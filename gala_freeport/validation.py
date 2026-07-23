from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite
from pathlib import Path
from statistics import median
from typing import Any
import json

from .models import CatalogObservation
from .storage import read_jsonl_gz, snapshot_files


class ValidationError(RuntimeError):
    """One or more production integrity gates rejected a collection."""


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    valid_price_percentage: float
    prior_overlap_percentage: float | None
    product_count_change_percentage: float | None
    duplicate_key_count: int
    rolling_14_day_median_products: float | None
    adaptive_product_floor: int | None
    errors: tuple[str, ...] = field(default_factory=tuple)


def _prior(snapshot_dir: Path, snapshot_date: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    dates = [path.name.split(".", 1)[0] for path in snapshot_files(snapshot_dir, "catalog")]
    eligible = [date for date in dates if date < snapshot_date]
    if not eligible:
        return [], None
    date = eligible[-1]
    rows = read_jsonl_gz(snapshot_dir / f"{date}.catalog.jsonl.gz")
    manifest_path = snapshot_dir / f"{date}.manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    return rows, manifest


def _healthy_counts(snapshot_dir: Path, snapshot_date: str) -> list[int]:
    counts: list[int] = []
    for path in snapshot_files(snapshot_dir, "manifest"):
        if path.name[:10] >= snapshot_date:
            continue
        value = json.loads(path.read_text())
        if value.get("status") == "healthy" and isinstance(value.get("unique_products"), int):
            counts.append(value["unique_products"])
    return counts[-14:]


def validate_collection(
    catalog: list[CatalogObservation],
    *,
    snapshot_dir: Path,
    snapshot_date: str,
    visible_root_count: int,
    visible_node_count: int,
    all_roots_succeeded: bool,
    api_totals_reconciled: bool,
    min_valid_price_percentage: float = 95.0,
    min_prior_overlap_percentage: float = 80.0,
    max_product_drop_percentage: float = 25.0,
) -> ValidationMetrics:
    errors: list[str] = []
    if not all_roots_succeeded:
        errors.append("not every discovered leaf category completed")
    if not api_totals_reconciled:
        errors.append("one or more category counts did not reconcile with API totals")
    if not catalog:
        errors.append("catalog contains no normalized products")
    keys = [row.product_key for row in catalog]
    duplicates = len(keys) - len(set(keys))
    if duplicates:
        errors.append(f"normalized product keys contain {duplicates} duplicates")
    missing_names = sum(not row.name.strip() for row in catalog)
    if missing_names:
        errors.append(f"{missing_names} products are missing normalized names")
    valid_prices = sum(1 for row in catalog if row.regular_price is not None and isfinite(row.regular_price) and row.regular_price > 0)
    valid_percentage = round(valid_prices / max(len(catalog), 1) * 100, 3)
    if valid_percentage < min_valid_price_percentage:
        errors.append(f"valid positive price rate {valid_percentage}% is below {min_valid_price_percentage}%")

    prior, prior_manifest = _prior(snapshot_dir, snapshot_date)
    overlap: float | None = None
    count_change: float | None = None
    if prior:
        prior_keys = {str(row["product_key"]) for row in prior}
        overlap = round(len(prior_keys & set(keys)) / len(prior_keys) * 100, 3)
        count_change = round((len(catalog) - len(prior)) / len(prior) * 100, 3)
        if overlap < min_prior_overlap_percentage:
            errors.append(f"prior-key overlap {overlap}% is below {min_prior_overlap_percentage}%")
        if count_change < -max_product_drop_percentage:
            errors.append(f"product count change {count_change}% exceeds allowed drop of {max_product_drop_percentage}%")
    if prior_manifest:
        prior_roots = len(prior_manifest.get("leaf_categories") or [])
        prior_nodes = int(prior_manifest.get("discovered_category_nodes") or 0)
        if prior_roots and visible_root_count < prior_roots * 0.75:
            errors.append(
                f"suspicious leaf-category contraction: {prior_roots} to {visible_root_count}"
            )
        if prior_nodes and visible_node_count < prior_nodes * 0.75:
            errors.append(
                f"suspicious category-tree contraction: {prior_nodes} to {visible_node_count}"
            )

    counts = _healthy_counts(snapshot_dir, snapshot_date)
    rolling = round(float(median(counts)), 3) if counts else None
    adaptive_floor = floor(rolling * 0.75) if rolling is not None else None
    if adaptive_floor is not None and len(catalog) < adaptive_floor:
        errors.append(f"catalog size {len(catalog)} is below adaptive floor {adaptive_floor}")
    metrics = ValidationMetrics(valid_percentage, overlap, count_change, duplicates, rolling, adaptive_floor, tuple(errors))
    if errors:
        raise ValidationError("; ".join(errors))
    return metrics
