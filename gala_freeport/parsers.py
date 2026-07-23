from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable

from .models import (
    CURRENCY,
    MARKET_REFERENCE,
    SEO_LOCATION,
    STORE_CODE,
    STORE_ID,
    STORE_NAME,
    STORE_SYSTEM_NAME,
    STOREFRONT_URL,
    CatalogObservation,
    PromotionObservation,
    finite_nonnegative,
)


class ContractError(ValueError):
    """The public storefront contract is incomplete or inconsistent."""


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").split())


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _scalars(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            result.update(_scalars(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_scalars(child))
    elif value is not None:
        result.add(_normalized(value))
    return result


def verify_store_identity(store_payload: Any, footer_payload: Any) -> dict[str, Any]:
    """Fail closed unless one store record identifies Freeport–Merrick exactly."""
    expected = {
        str(STORE_ID),
        STORE_CODE,
        STORE_SYSTEM_NAME,
        SEO_LOCATION,
        STORE_NAME,
    }
    candidates: list[tuple[int, dict[str, Any]]] = []
    for candidate in _walk_dicts(store_payload):
        values = _scalars(candidate)
        normalized_lower = {value.casefold() for value in values}
        if all(value.casefold() in normalized_lower for value in expected):
            candidates.append((len(values), candidate))
    if not candidates:
        raise ContractError(
            "Freeport–Merrick store record was not found"
        )
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ContractError("Freeport–Merrick store identity is ambiguous")
    selected = candidates[0][1]
    footer_values = " | ".join(sorted(_scalars(footer_payload))).casefold()
    if _normalized(MARKET_REFERENCE).casefold() not in footer_values:
        raise ContractError("footer identity does not contain the expected Freeport address")
    canonical = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "record": selected,
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def parse_price(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return finite_nonnegative(value)
    matches = re.findall(r"(?<!\d)(\d+(?:,\d{3})*(?:\.\d+)?)", str(value))
    if not matches:
        return None
    return finite_nonnegative(matches[0].replace(",", ""))


def product_key(source_id: Any) -> str:
    if source_id is None or not str(source_id).strip():
        raise ContractError("product is missing source Id")
    return f"gala:store:{STORE_ID}:product:{str(source_id).strip()}"


def parse_products_response(
    payload: Any,
    *,
    requested_page: int,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Decode and validate My Cloud Grocer's JSON-inside-JSON page."""
    if not isinstance(payload, dict):
        raise ContractError("product response must be an object")
    total = payload.get("productsCount")
    pager = payload.get("pager")
    embedded = payload.get("productsJson")
    # The live storefront uses -1 for an empty, visible leaf. Accept only the
    # exact sentinel combination; any negative count with data still fails.
    if (
        total == -1
        and isinstance(pager, dict)
        and pager.get("LastIndex") == 0
        and embedded == "[]"
        and payload.get("productsList") is None
    ):
        total = 0
    if not isinstance(total, int) or total < 0:
        raise ContractError("productsCount must be a non-negative integer")
    if not isinstance(pager, dict):
        raise ContractError("pager must be an object")
    page_size = pager.get("PageSize")
    page_number = pager.get("PageNumber")
    last_index = pager.get("LastIndex")
    if not all(isinstance(value, int) for value in (page_size, page_number, last_index)):
        raise ContractError("pager PageSize, PageNumber, and LastIndex must be integers")
    if page_size <= 0 or page_number != requested_page or last_index < 0:
        raise ContractError("pager values violate the requested page contract")
    expected_last = (total + page_size - 1) // page_size
    if last_index != expected_last:
        raise ContractError(
            f"pager LastIndex {last_index} does not match total/page size {expected_last}"
        )
    if embedded is None:
        products: Any = []
    elif isinstance(embedded, str):
        try:
            products = json.loads(embedded)
        except json.JSONDecodeError as error:
            raise ContractError("productsJson is not valid embedded JSON") from error
    else:
        raise ContractError("productsJson must be a JSON string or null")
    if not isinstance(products, list) or any(not isinstance(item, dict) for item in products):
        raise ContractError("decoded productsJson must be an array of objects")
    if len(products) > page_size:
        raise ContractError("product page exceeds pager PageSize")
    if total == 0 and products:
        raise ContractError("zero-total response contains products")
    if total > 0 and not products:
        raise ContractError("nonzero product response contains an empty page")
    return total, page_size, last_index, products


def _category_ids(raw: dict[str, Any], source_category_id: str) -> list[str]:
    values = {str(source_category_id)}
    values.update(re.findall(r"(?:^|/c/)(\d+)(?:-\d+)?", str(raw.get("Cat") or "")))
    if raw.get("CatId") is not None:
        values.add(str(raw["CatId"]))
    return sorted(values)


def _unit_from_display(value: Any) -> str | None:
    match = re.search(r"/\s*([A-Za-z]+)", str(value or ""))
    return match.group(1).lower() if match else None


def _image_url(value: Any) -> str | None:
    path = str(value or "").strip()
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return f"https://galasupermarkets.com/api/content/images/thumbs/{path.lstrip('/')}"


def normalize_catalog_product(
    raw: dict[str, Any],
    observed_at: str,
    source_category_id: str,
    source_category_path: str,
) -> CatalogObservation:
    source_id = raw.get("Id")
    key = product_key(source_id)
    current_price = finite_nonnegative(raw.get("P_v"))
    if current_price is None:
        current_price = parse_price(raw.get("P"))
    original_price = parse_price(raw.get("O"))
    multi_quantity = finite_nonnegative(raw.get("PQ"))
    is_sale = _bool(raw.get("SP")) is True
    regular_price = original_price if original_price is not None and (is_sale or (multi_quantity or 0) > 1) else current_price
    promotion_ids = [promotion.promotion_id for promotion in normalize_promotions(raw, observed_at)]
    sp_id = str(raw["SPId"]) if raw.get("SPId") is not None else None
    sku = str(raw["SKU"]) if raw.get("SKU") not in (None, "") else None
    return CatalogObservation(
        product_key=key,
        retailer_product_id=str(source_id),
        catalog_product_id=sp_id,
        branch_product_id=None,
        source_id=str(source_id),
        sp_id=sp_id,
        sku=sku,
        name=_normalized(raw.get("N")),
        description=_normalized(raw.get("D")) or None,
        brand=_normalized(raw.get("Brand") or raw.get("brand")) or None,
        regular_price=regular_price,
        current_price=current_price,
        display_price=_normalized(raw.get("P")) or None,
        original_display_price=_normalized(raw.get("O")) or None,
        currency=CURRENCY,
        weight=None,
        unit_of_measure=_unit_from_display(raw.get("P")),
        unit_resolution=None,
        is_weighable=_bool(raw.get("iW")),
        is_out_of_stock=None,
        is_active=_bool(raw.get("Active")),
        is_visible=True,
        is_ebt_eligible=_bool(raw.get("EBT")),
        category_paths=[source_category_path],
        source_category_ids=_category_ids(raw, source_category_id),
        image_url=_image_url(raw.get("iU")),
        promotion_ids=sorted(set(promotion_ids)),
        observed_at=observed_at,
        source_url=f"{STOREFRONT_URL}/category/{source_category_id}",
    )


def _promotion(
    raw: dict[str, Any],
    observed_at: str,
    *,
    promotion_type: str,
    offer: dict[str, Any],
    effective: float | None,
    basis: str | None,
    description: str | None,
) -> PromotionObservation:
    key = product_key(raw.get("Id"))
    fingerprint = hashlib.sha256(
        json.dumps(offer, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    explicit_id = raw.get("BOGO_OfferId") if promotion_type == "bogo" else None
    promotion_id = str(explicit_id or f"{promotion_type}:{fingerprint}")
    return PromotionObservation(
        promotion_key=f"{key}:{promotion_id}",
        promotion_id=promotion_id,
        product_key=key,
        promotion_type=promotion_type,
        description=description,
        display_name=_normalized(raw.get("P")) or None,
        promotion_tag=_normalized(raw.get("SPRDN") or raw.get("CQ")) or None,
        valid_from=_normalized(raw.get("BOGO_ValidFrom")) or None,
        valid_to=_normalized(raw.get("BOGO_ValidBy")) or None,
        is_coupon=False,
        limit=None,
        first_level=None,
        levels=[],
        raw_offer_structure=copy.deepcopy(offer),
        derived_effective_unit_price=effective,
        derivation_basis=basis,
        observed_at=observed_at,
    )


def normalize_promotions(raw: dict[str, Any], observed_at: str) -> list[PromotionObservation]:
    """Normalize sale, quantity-for-price, and BOGO evidence independently."""
    result: list[PromotionObservation] = []
    current = finite_nonnegative(raw.get("P_v"))
    if current is None:
        current = parse_price(raw.get("P"))
    original = parse_price(raw.get("O"))
    quantity = finite_nonnegative(raw.get("PQ"))
    if quantity and quantity > 1 and current is not None:
        offer = {
            "quantity": quantity,
            "total_price": current,
            "display_price": raw.get("P"),
            "original_display_price": raw.get("O"),
            "source_fields": {"PQ": raw.get("PQ"), "PN": raw.get("PN"), "SPR": raw.get("SPR")},
        }
        result.append(
            _promotion(
                raw,
                observed_at,
                promotion_type="multi_buy",
                offer=offer,
                effective=round(current / quantity, 4),
                basis=f"explicit source quantity {quantity:g} for total ${current:g}",
                description=f"{quantity:g} for ${current:g}",
            )
        )
    elif _bool(raw.get("SP")) is True:
        offer = {
            "sale_price": current,
            "regular_price": original,
            "display_price": raw.get("P"),
            "original_display_price": raw.get("O"),
        }
        result.append(
            _promotion(
                raw,
                observed_at,
                promotion_type="sale",
                offer=offer,
                effective=current,
                basis="explicit P_v sale price" if current is not None else None,
                description=(
                    f"Sale ${current:g} (regular ${original:g})"
                    if current is not None and original is not None
                    else "Sale"
                ),
            )
        )
    if raw.get("BOGO_OfferId") not in (None, ""):
        buy = finite_nonnegative(raw.get("BOGO_BuyQty"))
        get = finite_nonnegative(raw.get("BOGO_GetQty"))
        percentage = finite_nonnegative(raw.get("BOGO_OfferPercentage"))
        offer = {
            "offer_id": raw.get("BOGO_OfferId"),
            "buy_quantity": buy,
            "get_quantity": get,
            "offer_percentage": percentage,
            "valid_from": raw.get("BOGO_ValidFrom"),
            "valid_to": raw.get("BOGO_ValidBy"),
        }
        effective = None
        basis = None
        if buy and get and current is not None and (percentage in (None, 100)):
            effective = round(current * buy / (buy + get), 4)
            basis = f"explicit buy {buy:g}, get {get:g} free"
        result.append(
            _promotion(
                raw,
                observed_at,
                promotion_type="bogo",
                offer=offer,
                effective=effective,
                basis=basis,
                description=f"Buy {buy:g}, get {get:g}" if buy and get else "BOGO offer",
            )
        )
    return result


def merge_product_observations(observations: Iterable[CatalogObservation]) -> list[CatalogObservation]:
    """Deduplicate leaf overlap and union category memberships."""
    merged: dict[str, CatalogObservation] = {}
    for observation in observations:
        existing = merged.get(observation.product_key)
        if existing is None:
            merged[observation.product_key] = observation
            continue
        comparable = (
            "source_id",
            "sp_id",
            "sku",
            "name",
            "regular_price",
            "current_price",
            "display_price",
            "original_display_price",
        )
        conflicts = [
            field
            for field in comparable
            if getattr(existing, field) != getattr(observation, field)
        ]
        if conflicts:
            raise ContractError(
                f"conflicting duplicate product {observation.product_key}: {', '.join(conflicts)}"
            )
        existing.category_paths = sorted(
            set(existing.category_paths) | set(observation.category_paths)
        )
        existing.source_category_ids = sorted(
            set(existing.source_category_ids) | set(observation.source_category_ids)
        )
        existing.promotion_ids = sorted(
            set(existing.promotion_ids) | set(observation.promotion_ids)
        )
    return [merged[key] for key in sorted(merged)]
