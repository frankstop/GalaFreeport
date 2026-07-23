from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .discovery import DiscoveryResult, discover_leaves, find_category
from .models import CategoryLeaf, STOREFRONT_URL
from .parsers import ContractError, parse_products_response, verify_store_identity

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://galasupermarkets.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
STORE_IDENTITY_PATH = "/api/multistore/StoresDialogJSON"
CATEGORY_TREE_PATH = "/api/AjaxFilter/GetCategoryTreeJSON?filterMode=00000000"
FOOTER_PATH = "/api/Common/FooterJSON"
PRODUCTS_PATH = "/api/AjaxFilter/JsonProductsList"
PRODUCT_CONTENT_TYPE = "application/x-www-form-urlencoded; charset=UTF-8"
USER_AGENT = "GalaFreeportResearch/1.0 (+https://github.com/frankstop/GalaFreeport)"
FORBIDDEN_PREFIXES = (
    "/api/customer",
    "/api/cart",
    "/api/checkout",
    "/api/order",
    "/api/address",
    "/api/loyalty",
    "/api/coupon",
    "/login",
    "/cart",
    "/checkout",
    "/account",
)


class SourceError(RuntimeError):
    """Anonymous browser acquisition failed closed."""


class PaginationError(SourceError):
    """A leaf page sequence violated the public API contract."""


@dataclass(frozen=True, slots=True)
class CategoryCollection:
    root: CategoryLeaf
    total: int
    products: tuple[dict[str, Any], ...]
    pages: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RobotsPolicy:
    text: str
    sha256: str
    crawl_delay: float


@dataclass(slots=True)
class RawCollection:
    store_identity: dict[str, Any]
    category_tree: list[dict[str, Any]]
    discovery: DiscoveryResult
    categories: list[CategoryCollection]
    robots: RobotsPolicy
    store_identity_sha256: str
    category_tree_sha256: str
    requests: int
    retries: int
    elapsed_seconds: float


class GlobalRateLimiter:
    """One serial minimum interval shared by every required public request."""

    def __init__(self, minimum_delay: float) -> None:
        self.minimum_delay = max(0.0, minimum_delay)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            remaining = self.minimum_delay - (time.monotonic() - self._last)
            if remaining > 0:
                time.sleep(remaining)
            self._last = time.monotonic()

    def raise_minimum(self, minimum_delay: float) -> None:
        self.minimum_delay = max(self.minimum_delay, minimum_delay)


def paginate_category(
    root: CategoryLeaf,
    fetch_page: Callable[[int], dict[str, Any]],
) -> CategoryCollection:
    """Fetch a leaf serially and reconcile every page to productsCount."""
    expected_total: int | None = None
    expected_last: int | None = None
    page_number = 1
    products: list[dict[str, Any]] = []
    pages: list[int] = []
    page_hashes: set[str] = set()
    product_ids: set[str] = set()
    while True:
        if page_number in pages:
            raise PaginationError(
                f"page loop at {page_number} for category {root.category_id}"
            )
        payload = fetch_page(page_number)
        try:
            total, _, last_index, page = parse_products_response(
                payload, requested_page=page_number
            )
        except ContractError as error:
            raise PaginationError(
                f"category {root.category_id} page {page_number}: {error}"
            ) from error
        pages.append(page_number)
        if expected_total is None:
            expected_total = total
            expected_last = last_index
        elif total != expected_total or last_index != expected_last:
            raise PaginationError(
                f"inconsistent totals for category {root.category_id}"
            )
        ids = [str(item.get("Id")) for item in page]
        if any(identifier == "None" for identifier in ids):
            raise PaginationError(
                f"category {root.category_id} contains a product without Id"
            )
        if len(ids) != len(set(ids)):
            raise PaginationError(
                f"category {root.category_id} page {page_number} contains duplicate Id values"
            )
        fingerprint = hashlib.sha256(
            json.dumps(ids, separators=(",", ":")).encode()
        ).hexdigest()
        if page and fingerprint in page_hashes:
            raise PaginationError(
                f"category {root.category_id} repeated page {page_number}"
            )
        page_hashes.add(fingerprint)
        duplicates = product_ids.intersection(ids)
        if duplicates:
            raise PaginationError(
                f"category {root.category_id} repeats product IDs across pages: "
                f"{sorted(duplicates)[:3]}"
            )
        product_ids.update(ids)
        products.extend(page)
        if len(products) > total:
            raise PaginationError(
                f"category {root.category_id} collected more than productsCount"
            )
        if last_index == 0 or page_number == last_index:
            break
        if not page:
            raise PaginationError(
                f"category {root.category_id} returned an empty intermediate page"
            )
        page_number += 1
    if expected_total is None or len(products) != expected_total:
        raise PaginationError(
            f"category {root.category_id} count mismatch: "
            f"collected={len(products)} total={expected_total}"
        )
    return CategoryCollection(root, expected_total, tuple(products), tuple(pages))


def parse_robots(text: str, requested_delay: float) -> RobotsPolicy:
    if not text.strip():
        raise SourceError("robots.txt is empty")
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(text.splitlines())
    paths = (
        STOREFRONT_URL,
        BASE_URL + STORE_IDENTITY_PATH,
        BASE_URL + CATEGORY_TREE_PATH,
        BASE_URL + PRODUCTS_PATH,
    )
    if not all(parser.can_fetch(USER_AGENT, path) for path in paths):
        raise SourceError(
            "robots.txt does not permit the configured storefront/category/product paths"
        )
    delay = parser.crawl_delay(USER_AGENT)
    if delay is None:
        delay = parser.crawl_delay("*")
    delay_value = float(delay or 0)
    return RobotsPolicy(
        text,
        hashlib.sha256(text.encode()).hexdigest(),
        max(delay_value, requested_delay),
    )


class BrowserSource:
    """Clean-context Playwright source for the anonymous public catalog."""

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 1.5,
        retry_count: int = 2,
        timeout_seconds: float = 45.0,
        diagnostic_limit: int | None = None,
    ) -> None:
        self.headless = headless
        self.request_delay = request_delay
        self.retry_count = max(0, retry_count)
        self.timeout_ms = int(timeout_seconds * 1000)
        self.diagnostic_limit = diagnostic_limit
        self.requests = 0
        self.retries = 0
        self._limiter = GlobalRateLimiter(request_delay)

    def _route(self, route: Any) -> None:
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.casefold()
        if parsed.hostname == "galasupermarkets.com" and any(
            path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES
        ):
            route.abort("blockedbyclient")
            return
        if request.resource_type in {"image", "font", "media"}:
            route.abort("blockedbyclient")
        else:
            route.continue_()

    def _fetch_robots(self) -> RobotsPolicy:
        self._limiter.wait()
        self.requests += 1
        request = Request(
            ROBOTS_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain, text/*;q=0.9, */*;q=0.1",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_ms / 1000) as response:
                status = int(response.status)
                content_type = str(response.headers.get("content-type", ""))
                charset = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(charset)
        except HTTPError as error:
            raise SourceError(
                f"robots.txt returned HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, UnicodeDecodeError) as error:
            raise SourceError(f"robots.txt request failed: {error}") from error
        if status >= 400 or "text" not in content_type.casefold():
            raise SourceError(
                f"robots.txt returned HTTP {status} content type {content_type!r}"
            )
        return parse_robots(text, self.request_delay)

    def _fetch_json(
        self,
        page: Page,
        path: str,
        *,
        method: str = "GET",
        body: Any = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            if attempt:
                self.retries += 1
                time.sleep(min(2 ** (attempt - 1), 8))
            self._limiter.wait()
            self.requests += 1
            try:
                result = page.evaluate(
                    """async ({path, method, body, productContentType}) => {
                      const headers = {
                        'accept': '*/*',
                        'X-Requested-With': 'XMLHttpRequest'
                      };
                      // My Cloud Grocer expects a raw JSON string while declaring
                      // the legacy form MIME type used by its own storefront.
                      if (body !== null) {
                        headers['content-type'] = productContentType;
                      }
                      const response = await fetch(path, {
                        method,
                        headers,
                        credentials: 'same-origin',
                        body: body === null ? undefined : JSON.stringify(body)
                      });
                      return {
                        status: response.status,
                        type: response.headers.get('content-type') || '',
                        text: await response.text()
                      };
                    }""",
                    {
                        "path": path,
                        "method": method,
                        "body": body,
                        "productContentType": PRODUCT_CONTENT_TYPE,
                    },
                )
                status = int(result["status"])
                content_type = str(result["type"])
                text = str(result["text"])
                if status in {401, 403}:
                    raise SourceError(
                        f"required public endpoint returned HTTP {status}; failing closed"
                    )
                if status >= 400:
                    raise SourceError(f"required public endpoint returned HTTP {status}")
                if "json" not in content_type.casefold():
                    raise SourceError(
                        f"required public endpoint returned non-JSON content type "
                        f"{content_type!r}"
                    )
                return json.loads(text)
            except (json.JSONDecodeError, SourceError, Exception) as error:
                last_error = error
                if isinstance(error, SourceError) and (
                    "HTTP 401" in str(error) or "HTTP 403" in str(error)
                ):
                    break
        raise SourceError(
            f"request failed after bounded retries: {last_error}"
        ) from last_error

    @staticmethod
    def _product_body(category_id: str) -> list[dict[str, Any]]:
        return [
            {"FilterType": 0, "Value1": str(category_id), "categoryId": 0},
            {
                "FilterType": 0,
                "Value1": str(category_id),
                "categoryId": str(category_id),
            },
        ]

    def collect(self, category_id: str | None = None) -> RawCollection:
        started = time.monotonic()
        playwright: Playwright | None = None
        browser: Browser | None = None
        context: BrowserContext | None = None
        try:
            robots = self._fetch_robots()
            self._limiter.raise_minimum(robots.crawl_delay)
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=USER_AGENT,
                storage_state=None,
                locale="en-US",
            )
            context.set_default_timeout(self.timeout_ms)
            context.route("**/*", self._route)
            page = context.new_page()
            self._limiter.wait()
            self.requests += 1
            response = page.goto(
                STOREFRONT_URL,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )
            if response is None or response.status >= 400:
                raise SourceError(
                    f"storefront returned HTTP {response.status if response else 'no response'}"
                )
            if page.url.rstrip("/") != STOREFRONT_URL.rstrip("/"):
                raise SourceError(f"storefront resolved to unexpected URL {page.url!r}")
            store_payload = self._fetch_json(page, STORE_IDENTITY_PATH)
            footer_payload = self._fetch_json(page, FOOTER_PATH)
            identity = verify_store_identity(store_payload, footer_payload)
            category_payload = self._fetch_json(page, CATEGORY_TREE_PATH)
            if not isinstance(category_payload, list):
                raise SourceError("category tree endpoint did not return an array")
            discovery = discover_leaves(category_payload)
            leaves = list(discovery.leaves)
            if category_id is not None:
                leaves = [find_category(category_payload, str(category_id))]
            elif self.diagnostic_limit is not None:
                leaves = leaves[: self.diagnostic_limit]
            categories: list[CategoryCollection] = []
            for index, leaf in enumerate(leaves, 1):
                LOGGER.info(
                    "leaf_start",
                    extra={
                        "category_id": leaf.category_id,
                        "index": index,
                        "total_leaves": len(leaves),
                    },
                )
                category = paginate_category(
                    leaf,
                    lambda page_number, leaf_id=leaf.category_id: self._fetch_json(
                        page,
                        f"{PRODUCTS_PATH}?pageNumber={page_number}&filterMode=00000000",
                        method="POST",
                        body=self._product_body(leaf_id),
                    ),
                )
                categories.append(category)
                LOGGER.info(
                    "leaf_complete",
                    extra={
                        "category_id": leaf.category_id,
                        "products": category.total,
                        "pages": len(category.pages),
                    },
                )
            category_canonical = json.dumps(
                category_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            return RawCollection(
                store_identity=identity["record"],
                category_tree=category_payload,
                discovery=discovery,
                categories=categories,
                robots=robots,
                store_identity_sha256=identity["sha256"],
                category_tree_sha256=hashlib.sha256(
                    category_canonical.encode()
                ).hexdigest(),
                requests=self.requests,
                retries=self.retries,
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
        except Exception as error:
            lowered = str(error).casefold()
            if "captcha" in lowered or "authentication" in lowered:
                raise SourceError(
                    f"public anonymous contract unavailable: {error}"
                ) from error
            raise
        finally:
            if context is not None:
                context.close()
            if browser is not None:
                browser.close()
            if playwright is not None:
                playwright.stop()
