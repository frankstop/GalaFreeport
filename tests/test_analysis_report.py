from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from gala_freeport.analysis import build_daily_summary, build_price_change_history
from gala_freeport.catalog_history import build_catalog_history
from gala_freeport.parsers import normalize_catalog_product, normalize_promotions
from gala_freeport.report import ANALYTICS_MEASUREMENT_ID, build_reports
from gala_freeport.storage import write_snapshot_bundle


def row(identifier: int, price: float, observed: str, *, brand: str = "Brand"):
    return normalize_catalog_product(
        {
            "Id": identifier,
            "SPId": identifier + 1000,
            "SKU": f"{identifier:06d}",
            "N": f"Item {identifier}",
            "brand": brand,
            "iU": f"https://images.example/items/{{{{size}}}}/{identifier}.{{{{extension||'jpg'}}}}",
            "P": f"${price}",
            "P_v": price,
            "SP": False,
            "PQ": 1,
            "Active": "True",
            "CatId": 10,
        },
        observed,
        "10",
        "Produce > Fresh",
    )


class AnalysisReportTests(unittest.TestCase):
    def test_price_change_history_keeps_complete_multi_day_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshots = Path(temporary) / "data/snapshots"
            first = [row(identifier, 1 + identifier / 10, "2026-07-15T12:00:00Z") for identifier in range(1, 121)]
            second = [row(identifier, 2 + identifier / 10, "2026-07-16T12:00:00Z") for identifier in range(1, 121)]
            third = [
                row(identifier, (1.5 if identifier <= 20 else 2) + identifier / 10, "2026-07-18T12:00:00Z")
                for identifier in range(1, 121)
            ]
            write_snapshot_bundle(snapshots, "2026-07-15", first, [], {"status": "healthy"})
            write_snapshot_bundle(snapshots, "2026-07-16", second, [], {"status": "healthy"})
            write_snapshot_bundle(snapshots, "2026-07-18", third, [], {"status": "healthy"})

            index, shards = build_price_change_history(snapshots)

            self.assertEqual(index["status"], "comparison_available")
            self.assertEqual(index["snapshot_days"], 3)
            self.assertEqual(index["comparison_days"], 2)
            self.assertEqual(index["total_changes"], 140)
            self.assertEqual(index["price_increases"], 120)
            self.assertEqual(index["price_decreases"], 20)
            self.assertEqual(index["distinct_products"], 120)
            self.assertEqual(len(index["files"]), 2)
            self.assertEqual(len(shards["2026-07-16"]["changes"]), 120)
            self.assertEqual(len(shards["2026-07-18"]["changes"]), 20)
            self.assertEqual(shards["2026-07-18"]["changes"][0]["direction"], "decrease")
            self.assertEqual(index["filters"]["departments"], ["Produce"])
            self.assertEqual(index["filters"]["brands"], ["Brand"])

    def test_second_fixture_day_produces_changes_and_explicit_calendar_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshots, docs = root / "data/snapshots", root / "docs"
            docs.mkdir()
            (docs / "METHODOLOGY.md").write_text("# Methodology\n\nMissing days remain gaps.")
            first = [row(1, 2, "2026-07-15T12:00:00Z"), row(2, 4, "2026-07-15T12:00:00Z", brand="Other Brand")]
            second = [row(1, 3, "2026-07-17T12:00:00Z"), row(3, 5, "2026-07-17T12:00:00Z")]
            promoted_raw = {
                "Id": 1,
                "P": "$5.00",
                "O": "$3.00",
                "P_v": 5.0,
                "SP": True,
                "PQ": 2,
            }
            promotions = normalize_promotions(promoted_raw, "2026-07-17T12:00:00Z")
            write_snapshot_bundle(snapshots, "2026-07-15", first, [], {"status": "healthy", "observed_at": "2026-07-15T12:00:00Z"})
            write_snapshot_bundle(snapshots, "2026-07-17", second, promotions, {"status": "healthy", "observed_at": "2026-07-17T12:00:00Z"})
            summary = build_daily_summary(snapshots)
            self.assertEqual(summary["comparison"]["price_increases"], 1)
            self.assertEqual(summary["comparison"]["additions"], 1)
            self.assertEqual(summary["assortment_changes"]["additions"][0]["product_key"], "gala:store:6:product:3")
            index = build_catalog_history(snapshots, root / "history")
            self.assertEqual(index["calendar_days"], 3)
            self.assertEqual(index["total_items"], 3)
            self.assertEqual(index["filters"]["departments"], ["Produce"])
            self.assertEqual(index["filters"]["brands"], ["Brand", "Other Brand"])
            self.assertEqual(index["filters"]["price_range"], {"min": 3.0, "max": 5.0})
            item_one = next(item for item in index["items"] if item["retailer_product_id"] == "1")
            item_two = next(item for item in index["items"] if item["retailer_product_id"] == "2")
            self.assertEqual(item_one["latest_regular_price"], 3.0)
            self.assertEqual(item_one["latest_promotion_count"], 1)
            self.assertTrue(item_one["has_price_change"])
            self.assertEqual(item_one["observed_days"], 2)
            self.assertTrue(item_one["is_current"])
            self.assertFalse(item_two["is_current"])
            self.assertEqual(item_two["last_seen"], "2026-07-15")
            shard = item_one["shard"]
            import json
            detail = next(
                item
                for item in json.loads((root / "history" / f"{shard}.json").read_text())["items"]
                if item["product_key"] == item_one["product_key"]
            )
            self.assertIsNone(detail["observations"][1]["catalog"])
            self.assertEqual(detail["image_url"], "https://images.example/items/500/1.jpg")
            build_reports(snapshots, docs)
            first_build = {
                path.relative_to(docs).as_posix(): path.read_bytes()
                for path in docs.rglob("*")
                if path.is_file()
            }
            build_reports(snapshots, docs)
            second_build = {
                path.relative_to(docs).as_posix(): path.read_bytes()
                for path in docs.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_build, second_build)
            for name in ("index.html", "daily-report.html", "weekly-report.html", "price-changes.html", "catalog.html", "catalog-history.html", "METHODOLOGY.html"):
                self.assertTrue((docs / name).exists())
                if name != "catalog-history.html":
                    self.assertIn('src="assets/analytics.js?v=research-1.0"', (docs / name).read_text())
            analytics_js = (docs / "assets/analytics.js").read_text()
            self.assertIn(ANALYTICS_MEASUREMENT_ID, analytics_js)
            self.assertIn('traffic_context: window.self === window.top ? "direct" : "embedded"', analytics_js)
            catalog_html = (docs / "catalog.html").read_text()
            catalog_js = (docs / "assets/catalog.js").read_text()
            self.assertIn('<dd id="total-items">3</dd>', catalog_html)
            self.assertIn('id="detail-panel"', catalog_html)
            self.assertIn('id="department-filter"', catalog_html)
            self.assertIn("downloadFilteredCsv", catalog_js)
            self.assertNotIn("slice(0,100)", catalog_js)
            self.assertIn("catalog.html", (docs / "catalog-history.html").read_text())
            self.assertTrue((docs / "data/daily-summary.json").exists())
            price_index = json.loads((docs / "data/price-changes/index.json").read_text())
            self.assertEqual(price_index["total_changes"], 1)
            self.assertTrue((docs / "data/price-changes/2026-07-17.json").exists())
            price_html = (docs / "price-changes.html").read_text()
            price_js = (docs / "assets/price-changes.js").read_text()
            self.assertIn('id="change-from-date"', price_html)
            self.assertIn('id="change-detail-panel"', price_html)
            self.assertIn("downloadFilteredCsv", price_js)
            self.assertIn("downloadFilteredJson", price_js)


if __name__ == "__main__":
    unittest.main()
