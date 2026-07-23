from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from gala_freeport.browser_source import (
    BrowserSource,
    PaginationError,
    PRODUCT_CONTENT_TYPE,
    SourceError,
    paginate_category,
    parse_robots,
)
from gala_freeport.models import CategoryLeaf


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class BrowserSourceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.leaf = CategoryLeaf(
            "10393",
            "Soda",
            ("Grocery", "Beverages", "Soda"),
            ("10387", "10384", "10393"),
        )

    def test_single_page_reconciles(self) -> None:
        result = paginate_category(
            self.leaf, lambda page: fixture("products_single.json")
        )
        self.assertEqual(result.total, 2)
        self.assertEqual(result.pages, (1,))
        self.assertEqual([row["Id"] for row in result.products], [355766, 355713])

    def test_multi_page_reconciles_using_page_number(self) -> None:
        pages = {
            1: fixture("products_multi_1.json"),
            2: fixture("products_multi_2.json"),
        }
        result = paginate_category(self.leaf, pages.__getitem__)
        self.assertEqual(result.total, 3)
        self.assertEqual(result.pages, (1, 2))
        self.assertEqual([row["Id"] for row in result.products], [1, 2, 3])

    def test_repeated_page_fails_closed(self) -> None:
        first = fixture("products_multi_1.json")
        second = copy.deepcopy(first)
        second["pager"]["PageNumber"] = 2
        with self.assertRaisesRegex(PaginationError, "repeats product IDs|repeated"):
            paginate_category(self.leaf, lambda page: first if page == 1 else second)

    def test_empty_intermediate_page_fails_closed(self) -> None:
        first = fixture("products_multi_1.json")
        first["productsJson"] = "[]"
        with self.assertRaisesRegex(PaginationError, "empty"):
            paginate_category(self.leaf, lambda page: first)

    def test_inconsistent_total_fails_closed(self) -> None:
        pages = {
            1: fixture("products_multi_1.json"),
            2: fixture("products_multi_2.json"),
        }
        pages[2]["productsCount"] = 4
        pages[2]["pager"]["LastIndex"] = 2
        with self.assertRaisesRegex(PaginationError, "inconsistent totals"):
            paginate_category(self.leaf, pages.__getitem__)

    def test_required_paths_must_be_allowed_by_robots(self) -> None:
        policy = parse_robots("User-agent: *\nAllow: /\nCrawl-delay: 2\n", 1.5)
        self.assertEqual(policy.crawl_delay, 2)
        with self.assertRaises(SourceError):
            parse_robots("User-agent: *\nDisallow: /api/\n", 1.5)

    def test_product_request_body_matches_observed_contract(self) -> None:
        self.assertEqual(
            PRODUCT_CONTENT_TYPE,
            "application/x-www-form-urlencoded; charset=UTF-8",
        )
        self.assertEqual(
            BrowserSource._product_body("11042"),
            [
                {"FilterType": 0, "Value1": "11042", "categoryId": 0},
                {"FilterType": 0, "Value1": "11042", "categoryId": "11042"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
