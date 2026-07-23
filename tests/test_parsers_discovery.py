from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from gala_freeport.discovery import discover_leaves, find_category
from gala_freeport.parsers import (
    ContractError,
    merge_product_observations,
    normalize_catalog_product,
    normalize_promotions,
    parse_products_response,
    product_key,
    verify_store_identity,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ParserDiscoveryTests(unittest.TestCase):
    def test_store_identity_selects_exact_freeport_record(self) -> None:
        identity = verify_store_identity(
            fixture("store_identity.json"), fixture("footer.json")
        )
        self.assertEqual(identity["record"]["Id"], 6)
        wrong = fixture("store_identity.json")
        wrong["stores"][0]["Code"] = "wrong"
        with self.assertRaises(ContractError):
            verify_store_identity(wrong, fixture("footer.json"))

    def test_category_tree_discovers_every_leaf_and_paths(self) -> None:
        tree = fixture("category_tree.json")
        discovery = discover_leaves(tree)
        self.assertEqual(discovery.total_nodes, 6)
        self.assertEqual(discovery.root_nodes, 2)
        self.assertEqual(discovery.leaf_nodes, 3)
        soda = find_category(tree, "10393")
        self.assertEqual(soda.path_names, ("Grocery", "Beverages", "Soda"))
        self.assertEqual(soda.path_ids, ("10387", "10384", "10393"))

    def test_json_inside_json_contract(self) -> None:
        payload = fixture("products_single.json")
        total, page_size, last, rows = parse_products_response(
            payload, requested_page=1
        )
        self.assertEqual((total, page_size, last, len(rows)), (2, 120, 1, 2))
        bad = copy.deepcopy(payload)
        bad["productsJson"] = "not json"
        with self.assertRaises(ContractError):
            parse_products_response(bad, requested_page=1)

    def test_regular_sale_weighted_multibuy_bogo_and_missing_prices(self) -> None:
        rows = fixture("products_variety.json")
        normalized = [
            normalize_catalog_product(
                row, "2026-07-23T09:00:00Z", "10393", "Grocery > Beverages > Soda"
            )
            for row in rows
        ]
        self.assertEqual(normalized[0].regular_price, 4.99)
        self.assertEqual(normalized[1].regular_price, 3.69)
        self.assertEqual(normalized[1].current_price, 2.49)
        self.assertTrue(normalized[1].is_weighable)
        self.assertEqual(normalized[2].regular_price, 2.79)
        self.assertIsNone(normalized[4].regular_price)
        self.assertEqual(normalized[0].source_id, "101")
        self.assertEqual(normalized[0].sp_id, "201")
        self.assertEqual(normalized[0].sku, "000101")
        self.assertEqual(
            normalized[0].product_key, "gala:store:6:product:101"
        )

        sale = normalize_promotions(rows[1], "2026-07-23T09:00:00Z")
        self.assertEqual(sale[0].promotion_type, "sale")
        multibuy = normalize_promotions(rows[2], "2026-07-23T09:00:00Z")
        self.assertEqual(multibuy[0].promotion_type, "multi_buy")
        self.assertEqual(multibuy[0].derived_effective_unit_price, 2.5)
        bogo = normalize_promotions(rows[3], "2026-07-23T09:00:00Z")
        self.assertEqual(bogo[0].promotion_type, "bogo")
        self.assertEqual(bogo[0].derived_effective_unit_price, 3.0)

    def test_deduplication_unions_categories_and_rejects_conflicts(self) -> None:
        row = fixture("products_variety.json")[0]
        first = normalize_catalog_product(
            row, "2026-07-23T09:00:00Z", "10393", "Grocery > Beverages > Soda"
        )
        second = normalize_catalog_product(
            row, "2026-07-23T09:00:00Z", "999", "Specials"
        )
        merged = merge_product_observations([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(
            merged[0].category_paths, ["Grocery > Beverages > Soda", "Specials"]
        )
        conflict = copy.deepcopy(row)
        conflict["P_v"] = 9.99
        conflict["P"] = "$9.99"
        third = normalize_catalog_product(
            conflict, "2026-07-23T09:00:00Z", "999", "Specials"
        )
        with self.assertRaises(ContractError):
            merge_product_observations([first, third])

    def test_stable_key_requires_source_id(self) -> None:
        self.assertEqual(product_key(44), "gala:store:6:product:44")
        with self.assertRaises(ContractError):
            product_key(None)

    def test_blank_source_name_uses_traceable_placeholder(self) -> None:
        row = fixture("products_variety.json")[0]
        row["N"] = " "
        product = normalize_catalog_product(
            row,
            "2026-07-23T09:00:00Z",
            "10393",
            "Grocery > Beverages > Soda",
        )
        self.assertEqual(
            product.name,
            f"[Unnamed source product {row['Id']}]",
        )


if __name__ == "__main__":
    unittest.main()
