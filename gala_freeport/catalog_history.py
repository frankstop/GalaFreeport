from __future__ import annotations

from datetime import date, timedelta
import hashlib
from pathlib import Path
from typing import Any

from .storage import read_jsonl_gz, snapshot_files, write_json


def _date_range(start: str, end: str) -> list[str]:
    current, finish = date.fromisoformat(start), date.fromisoformat(end)
    result: list[str] = []
    while current <= finish:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _display_image_url(value: Any) -> str | None:
    """Resolve the public storefront's image template for static display."""
    if not value:
        return None
    return (
        str(value)
        .replace("{{size}}", "500")
        .replace("{{extension||'jpg'}}", "jpg")
        .replace('{{extension||"jpg"}}', "jpg")
    )


def _department(path: str) -> str:
    return path.split(">", 1)[0].strip()


def build_catalog_history(snapshot_dir: Path, output_dir: Path) -> dict[str, Any]:
    files = snapshot_files(snapshot_dir, "catalog")
    if not files:
        raise ValueError("no catalog snapshots found")
    dated = [(path.name[:10], read_jsonl_gz(path)) for path in files]
    days = _date_range(dated[0][0], dated[-1][0])
    items: dict[str, dict[str, Any]] = {}
    observations: dict[str, dict[str, dict[str, Any]]] = {}
    for snapshot_date, rows in dated:
        for row in rows:
            key = str(row["product_key"])
            previous_paths = items.get(key, {}).get("category_paths", [])
            category_paths = sorted(set(previous_paths) | set(row.get("category_paths", [])))
            items[key] = {
                "product_key": key,
                "name": row.get("name"),
                "brand": row.get("brand"),
                "category_paths": category_paths,
                "retailer_product_id": row.get("retailer_product_id"),
                "catalog_product_id": row.get("catalog_product_id"),
                "branch_product_id": row.get("branch_product_id"),
                "source_id": row.get("source_id"),
                "sp_id": row.get("sp_id"),
                "sku": row.get("sku"),
                "description": row.get("description"),
                "image_url": _display_image_url(row.get("image_url")),
                "weight": row.get("weight"),
                "unit_of_measure": row.get("unit_of_measure"),
                "unit_resolution": row.get("unit_resolution"),
                "is_weighable": row.get("is_weighable"),
                "is_active": row.get("is_active"),
                "is_visible": row.get("is_visible"),
                "currency": row.get("currency"),
                "source_url": row.get("source_url"),
            }
            observations.setdefault(key, {})[snapshot_date] = {
                "regular_price": row.get("regular_price"),
                "current_price": row.get("current_price"),
                "display_price": row.get("display_price"),
                "original_display_price": row.get("original_display_price"),
                "promotion_ids": row.get("promotion_ids", []),
                "is_out_of_stock": row.get("is_out_of_stock"),
            }
    promotions: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for path in snapshot_files(snapshot_dir, "promotions"):
        snapshot_date = path.name[:10]
        for row in read_jsonl_gz(path):
            promotions.setdefault(str(row["product_key"]), {}).setdefault(snapshot_date, []).append({
                "promotion_id": row.get("promotion_id"),
                "description": row.get("description") or row.get("display_name"),
                "derived_effective_unit_price": row.get("derived_effective_unit_price"),
                "derivation_basis": row.get("derivation_basis"),
            })
    shards: dict[str, list[dict[str, Any]]] = {}
    index_items: list[dict[str, Any]] = []
    latest_day = days[-1]
    for key in sorted(items):
        shard = hashlib.sha256(key.encode()).hexdigest()[:2]
        item_observations = observations.get(key, {})
        observed_dates = sorted(item_observations)
        latest_catalog = item_observations.get(latest_day)
        last_catalog = item_observations[observed_dates[-1]]
        prices = [
            observation.get("regular_price")
            for observation in item_observations.values()
            if observation.get("regular_price") is not None
        ]
        latest_promotions = promotions.get(key, {}).get(latest_day, [])
        departments = sorted({_department(path) for path in items[key]["category_paths"] if path})
        browse_fields = {
            "departments": departments,
            "latest_regular_price": last_catalog.get("regular_price"),
            "latest_promotion_count": len(latest_promotions),
            "is_current": latest_catalog is not None,
            "first_seen": observed_dates[0],
            "last_seen": observed_dates[-1],
            "observed_days": len(observed_dates),
            "has_price_change": len(set(prices)) > 1,
        }
        item = {
            **items[key],
            **browse_fields,
            "observations": [
                {
                    "date": day,
                    "catalog": observations.get(key, {}).get(day),
                    "promotions": promotions.get(key, {}).get(day, []),
                }
                for day in days
            ],
        }
        shards.setdefault(shard, []).append(item)
        index_items.append({
            "product_key": key,
            "name": items[key]["name"],
            "brand": items[key]["brand"],
            "category_paths": items[key]["category_paths"],
            "retailer_product_id": items[key]["retailer_product_id"],
            "catalog_product_id": items[key]["catalog_product_id"],
            "branch_product_id": items[key]["branch_product_id"],
            "source_id": items[key]["source_id"],
            "sp_id": items[key]["sp_id"],
            "sku": items[key]["sku"],
            **browse_fields,
            "shard": shard,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    for shard, rows in sorted(shards.items()):
        write_json(output_dir / f"{shard}.json", {"schema_version": "1.1", "items": rows})
    latest_prices = [
        item["latest_regular_price"]
        for item in index_items
        if item["latest_regular_price"] is not None
    ]
    index = {
        "schema_version": "1.1",
        "from_date": days[0],
        "to_date": days[-1],
        "calendar_days": len(days),
        "total_items": len(index_items),
        "filters": {
            "departments": sorted({department for item in index_items for department in item["departments"]}),
            "brands": sorted({str(item["brand"]) for item in index_items if item.get("brand")}, key=str.casefold),
            "price_range": {
                "min": min(latest_prices) if latest_prices else None,
                "max": max(latest_prices) if latest_prices else None,
            },
        },
        "items": index_items,
    }
    write_json(output_dir / "index.json", index)
    return index
