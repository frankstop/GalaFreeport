from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from math import isfinite
from pathlib import Path
from statistics import mean, median
from typing import Any

from .storage import read_jsonl_gz, snapshot_files

ANALYSIS_SCHEMA_VERSION = "1.0"


def _snapshot_date(path: Path) -> str:
    return path.name.split(".", 1)[0]


def _keyed(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key) is not None}


def _price(row: dict[str, Any] | None) -> float | None:
    if not row or row.get("regular_price") is None:
        return None
    try:
        value = float(row["regular_price"])
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) and value >= 0 else None


def _daily_stats(snapshot_date: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [price for row in rows if (price := _price(row)) is not None and price > 0]
    return {
        "snapshot_date": snapshot_date,
        "catalog_size": len(rows),
        "valid_price_percentage": round(len(prices) / max(len(rows), 1) * 100, 3),
        "median_regular_price": round(median(prices), 2) if prices else None,
        "average_regular_price": round(mean(prices), 2) if prices else None,
        "products_with_promotions": sum(1 for row in rows if row.get("promotion_ids")),
    }


def _mad(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    center = median(values)
    return center, median(abs(value - center) for value in values)


def compare_days(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    seen_before: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    previous_keys, current_keys = set(previous), set(current)
    common = previous_keys & current_keys
    changes: list[dict[str, Any]] = []
    for key in sorted(common):
        old_price, new_price = _price(previous[key]), _price(current[key])
        if old_price is None or new_price is None or old_price <= 0 or old_price == new_price:
            continue
        difference = round(new_price - old_price, 4)
        percentage = round(difference / old_price * 100, 3)
        changes.append({
            "product_key": key,
            "name": current[key].get("name") or previous[key].get("name"),
            "brand": current[key].get("brand"),
            "category_paths": current[key].get("category_paths", []),
            "previous_regular_price": old_price,
            "current_regular_price": new_price,
            "change": difference,
            "change_percentage": percentage,
        })
    percentages = [row["change_percentage"] for row in changes]
    center, spread = _mad(percentages)
    anomalies = []
    for row in changes:
        robust_z = 0.6745 * (row["change_percentage"] - center) / spread if spread else 0.0
        if abs(row["change_percentage"]) >= 20 and abs(robust_z) >= 3.5:
            anomalies.append({**row, "robust_z_score": round(robust_z, 3)})
    new_keys = current_keys - previous_keys
    additions = new_keys - (seen_before or set())
    returns = new_keys & (seen_before or set())
    comparison = {
        "prior_overlap_percentage": round(len(common) / max(len(previous_keys), 1) * 100, 3),
        "assortment_churn_percentage": round(len(previous_keys ^ current_keys) / max(len(previous_keys | current_keys), 1) * 100, 3),
        "matched_products": len(common),
        "price_increases": sum(row["change"] > 0 for row in changes),
        "price_decreases": sum(row["change"] < 0 for row in changes),
        "unchanged_or_uncomparable_prices": len(common) - len(changes),
        "additions": len(additions),
        "returns": len(returns),
        "missing_products": len(previous_keys - current_keys),
        "anomalies": len(anomalies),
    }
    return comparison, changes, anomalies


def _promotion_comparison(previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> dict[str, Any]:
    old_keys, new_keys = set(previous), set(current)
    common = old_keys & new_keys
    changed = [
        key for key in common
        if previous[key].get("raw_offer_structure") != current[key].get("raw_offer_structure")
        or previous[key].get("valid_to") != current[key].get("valid_to")
    ]
    starts, ends = sorted(new_keys - old_keys), sorted(old_keys - new_keys)
    return {
        "starts": starts,
        "ends": ends,
        "changes": sorted(changed),
        "start_count": len(starts),
        "end_count": len(ends),
        "change_count": len(changed),
        "active": len(current),
    }


def _group_summary(rows: list[dict[str, Any]], field: str, limit: int = 30) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    counts: Counter[str] = Counter()
    for row in rows:
        values = row.get(field)
        labels = values if isinstance(values, list) else [values]
        for label in labels:
            if not label:
                continue
            label = str(label)
            counts[label] += 1
            price = _price(row)
            if price is not None and price > 0:
                groups[label].append(price)
    return [
        {
            "name": label,
            "products": count,
            "median_regular_price": round(median(groups[label]), 2) if groups[label] else None,
        }
        for label, count in counts.most_common(limit)
    ]


def _window_history(
    dated: list[tuple[str, dict[str, dict[str, Any]]]], latest: dict[str, dict[str, Any]], days: int
) -> dict[str, Any]:
    if not dated:
        return {"days": days, "from_date": None, "to_date": None, "fully_observed_products": 0, "changed_products": 0}
    end = date.fromisoformat(dated[-1][0])
    start = end - timedelta(days=days - 1)
    selected = [(day, rows) for day, rows in dated if date.fromisoformat(day) >= start]
    full = 0
    changed = 0
    for key in latest:
        observations = [_price(rows.get(key)) for _, rows in selected]
        if len(observations) == len(selected) and all(value is not None for value in observations):
            full += 1
            if len(set(observations)) > 1:
                changed += 1
    return {
        "days": days,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "snapshot_days": len(selected),
        "fully_observed_products": full,
        "changed_products": changed,
    }


def _top_departments(paths: list[Any]) -> list[str]:
    return sorted({str(path).split(">", 1)[0].strip() for path in paths if str(path).strip()})


def build_price_change_history(snapshot_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Build a complete, date-sharded regular-price change contract."""
    catalog_files = snapshot_files(snapshot_dir, "catalog")
    if not catalog_files:
        raise ValueError("no catalog snapshots found")
    dates = [_snapshot_date(path) for path in catalog_files]
    keyed = [_keyed(read_jsonl_gz(path), "product_key") for path in catalog_files]
    shards: dict[str, dict[str, Any]] = {}
    file_rows: list[dict[str, Any]] = []
    all_changes: list[dict[str, Any]] = []
    seen = set(keyed[0])
    for position in range(1, len(keyed)):
        from_date, to_date = dates[position - 1], dates[position]
        comparison, changes, anomalies = compare_days(keyed[position - 1], keyed[position], seen)
        anomaly_keys = {row["product_key"] for row in anomalies}
        normalized_changes: list[dict[str, Any]] = []
        for change in changes:
            key = change["product_key"]
            source = keyed[position].get(key) or keyed[position - 1][key]
            departments = _top_departments(change.get("category_paths", []))
            normalized_changes.append({
                "event_key": f"{from_date}:{to_date}:{key}",
                "from_date": from_date,
                "to_date": to_date,
                "calendar_gap_days": (date.fromisoformat(to_date) - date.fromisoformat(from_date)).days,
                **change,
                "absolute_change": round(abs(change["change"]), 4),
                "absolute_change_percentage": round(abs(change["change_percentage"]), 3),
                "direction": "increase" if change["change"] > 0 else "decrease",
                "is_anomaly": key in anomaly_keys,
                "departments": departments,
                "retailer_product_id": source.get("retailer_product_id"),
                "catalog_product_id": source.get("catalog_product_id"),
                "branch_product_id": source.get("branch_product_id"),
                "source_id": source.get("source_id"),
                "sp_id": source.get("sp_id"),
                "sku": source.get("sku"),
            })
        increases = sum(row["direction"] == "increase" for row in normalized_changes)
        decreases = len(normalized_changes) - increases
        shard = {
            "schema_version": "1.0",
            "report": "price_changes_day",
            "from_date": from_date,
            "to_date": to_date,
            "comparison": comparison,
            "total_changes": len(normalized_changes),
            "price_increases": increases,
            "price_decreases": decreases,
            "changes": normalized_changes,
        }
        shards[to_date] = shard
        file_rows.append({
            "from_date": from_date,
            "to_date": to_date,
            "path": f"{to_date}.json",
            "total_changes": len(normalized_changes),
            "price_increases": increases,
            "price_decreases": decreases,
            "anomalies": len(anomalies),
            "matched_products": comparison["matched_products"],
        })
        all_changes.extend(normalized_changes)
        seen.update(keyed[position])
    prices = [
        price
        for row in all_changes
        for price in (row["previous_regular_price"], row["current_regular_price"])
    ]
    percentages = [row["change_percentage"] for row in all_changes]
    index = {
        "schema_version": "1.0",
        "report": "price_changes",
        "status": "comparison_available" if file_rows else "baseline_established",
        "scope": "Gala Freeport–Merrick public online regular prices; not asserted as physical shelf prices",
        "from_date": dates[0],
        "to_date": dates[-1],
        "snapshot_days": len(dates),
        "comparison_days": len(file_rows),
        "total_changes": len(all_changes),
        "price_increases": sum(row["direction"] == "increase" for row in all_changes),
        "price_decreases": sum(row["direction"] == "decrease" for row in all_changes),
        "distinct_products": len({row["product_key"] for row in all_changes}),
        "files": file_rows,
        "available_snapshot_dates": dates,
        "filters": {
            "departments": sorted({department for row in all_changes for department in row["departments"]}),
            "brands": sorted({str(row["brand"]) for row in all_changes if row.get("brand")}, key=str.casefold),
            "price_range": {"min": min(prices) if prices else None, "max": max(prices) if prices else None},
            "percentage_range": {"min": min(percentages) if percentages else None, "max": max(percentages) if percentages else None},
        },
        "methodology": {
            "comparison": "adjacent healthy snapshot dates matched by stable retailer listing key",
            "missingness": "an item must have finite positive regular prices on both dates; gaps are not changes",
            "completeness": "daily shard files contain every comparable regular-price change without a display cap",
            "anomaly_rule": "absolute price change >=20% and robust MAD z-score >=3.5",
        },
    }
    return index, shards


def build_daily_summary(snapshot_dir: Path) -> dict[str, Any]:
    catalog_files = snapshot_files(snapshot_dir, "catalog")
    if not catalog_files:
        raise ValueError("no catalog snapshots found")
    catalogs = [read_jsonl_gz(path) for path in catalog_files]
    dates = [_snapshot_date(path) for path in catalog_files]
    keyed = [_keyed(rows, "product_key") for rows in catalogs]
    daily = [_daily_stats(day, rows) for day, rows in zip(dates, catalogs)]
    comparisons: list[dict[str, Any]] = []
    all_changes: list[list[dict[str, Any]]] = []
    all_anomalies: list[list[dict[str, Any]]] = []
    seen: set[str] = set(keyed[0])
    for index in range(1, len(keyed)):
        comparison, changes, anomalies = compare_days(keyed[index - 1], keyed[index], seen)
        comparisons.append({"from_date": dates[index - 1], "to_date": dates[index], **comparison})
        all_changes.append(changes)
        all_anomalies.append(anomalies)
        seen.update(keyed[index])

    promotions_by_date: dict[str, dict[str, dict[str, Any]]] = {}
    for path in snapshot_files(snapshot_dir, "promotions"):
        promotions_by_date[_snapshot_date(path)] = _keyed(read_jsonl_gz(path), "promotion_key")
    latest_promotions = promotions_by_date.get(dates[-1], {})
    previous_promotions = promotions_by_date.get(dates[-2], {}) if len(dates) > 1 else {}
    promotion_change = _promotion_comparison(previous_promotions, latest_promotions)

    manifests = []
    for path in snapshot_files(snapshot_dir, "manifest"):
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    latest_changes = all_changes[-1] if all_changes else []
    latest_anomalies = all_anomalies[-1] if all_anomalies else []
    latest_rows = catalogs[-1]
    assortment_changes = {"additions": [], "returns": [], "missing_products": []}
    if len(keyed) > 1:
        previous_keys, current_keys = set(keyed[-2]), set(keyed[-1])
        historical_keys = set().union(*(set(day) for day in keyed[:-2])) if len(keyed) > 2 else set()
        for key in sorted(current_keys - previous_keys):
            bucket = "returns" if key in historical_keys else "additions"
            assortment_changes[bucket].append({
                "product_key": key, "name": keyed[-1][key].get("name"), "brand": keyed[-1][key].get("brand")
            })
        for key in sorted(previous_keys - current_keys):
            assortment_changes["missing_products"].append({
                "product_key": key, "name": keyed[-2][key].get("name"), "brand": keyed[-2][key].get("brand")
            })
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "report": "daily",
        "status": "comparison_available" if len(catalog_files) > 1 else "baseline_established",
        "scope": "Gala Freeport–Merrick public online catalog; not asserted as physical shelf prices",
        "latest_healthy_observation": manifests[-1].get("observed_at") if manifests else latest_rows[0].get("observed_at"),
        "latest": daily[-1],
        "previous": daily[-2] if len(daily) > 1 else None,
        "comparison": comparisons[-1] if comparisons else None,
        "daily_history": daily,
        "comparison_history": comparisons,
        "price_increases": sorted((row for row in latest_changes if row["change"] > 0), key=lambda row: -row["change_percentage"])[:100],
        "price_decreases": sorted((row for row in latest_changes if row["change"] < 0), key=lambda row: row["change_percentage"])[:100],
        "anomalies": sorted(latest_anomalies, key=lambda row: -abs(row["robust_z_score"]))[:50],
        "assortment_changes": assortment_changes,
        "promotion_changes": promotion_change,
        "active_promotions": list(latest_promotions.values()),
        "category_summary": _group_summary(latest_rows, "category_paths"),
        "brand_summary": _group_summary(latest_rows, "brand"),
        "price_history_windows": [_window_history(list(zip(dates, keyed)), keyed[-1], days) for days in (4, 7, 14, 28)],
        "snapshot_health_history": manifests,
        "methodology": {
            "identity": "My Cloud Grocer Id scoped to store 6; SPId and SKU are retained independently and SKU is not asserted to be a UPC",
            "missingness": "daily absence is preserved as a gap and is not treated as deletion or zero",
            "anomaly_rule": "absolute price change >=20% and robust MAD z-score >=3.5",
            "promotion_prices": "derived effective unit prices are labeled and never replace regular prices",
        },
    }


def build_weekly_summary(daily: dict[str, Any]) -> dict[str, Any]:
    history = daily["daily_history"][-7:]
    comparisons = daily["comparison_history"][-7:]
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "report": "weekly",
        "status": daily["status"],
        "scope": daily["scope"],
        "from_date": history[0]["snapshot_date"],
        "to_date": history[-1]["snapshot_date"],
        "snapshot_days": len(history),
        "latest_catalog_size": history[-1]["catalog_size"],
        "median_catalog_size": round(median(row["catalog_size"] for row in history), 1),
        "median_valid_price_percentage": round(median(row["valid_price_percentage"] for row in history), 3),
        "price_increases": sum(row["price_increases"] for row in comparisons),
        "price_decreases": sum(row["price_decreases"] for row in comparisons),
        "additions": sum(row["additions"] for row in comparisons),
        "returns": sum(row["returns"] for row in comparisons),
        "missing_products": sum(row["missing_products"] for row in comparisons),
        "daily_history": history,
        "comparison_history": comparisons,
        "category_summary": daily["category_summary"],
        "brand_summary": daily["brand_summary"],
        "snapshot_health_history": daily["snapshot_health_history"][-7:],
        "methodology": daily["methodology"],
    }
