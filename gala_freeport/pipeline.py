from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from zoneinfo import ZoneInfo

from .browser_source import BrowserSource
from .models import (
    CATEGORY_TREE_ID,
    MARKET_REFERENCE,
    SEO_LOCATION,
    STORE_CODE,
    STORE_ID,
    STORE_NAME,
    STORE_SYSTEM_NAME,
    Manifest,
)
from .parsers import merge_product_observations, normalize_catalog_product, normalize_promotions
from .report import build_reports
from .storage import write_snapshot_bundle
from .validation import validate_collection

LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _replace_directories_transactionally(staged: list[tuple[Path, Path]], backup_root: Path) -> None:
    """Replace complete output directories, restoring all on any failure."""
    backup_root.mkdir(parents=True, exist_ok=True)
    moved_old: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for _, target in staged:
            if target.exists():
                backup = backup_root / target.name
                os.replace(target, backup)
                moved_old.append((backup, target))
        for source, target in staged:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            installed.append(target)
    except BaseException:
        for target in installed:
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
        for backup, target in reversed(moved_old):
            os.replace(backup, target)
        raise


def run_pipeline(
    root: Path,
    *,
    snapshot_date: str | None = None,
    headless: bool = True,
    request_delay: float = 4.0,
    retry_count: int = 2,
    timeout_seconds: float = 45.0,
    diagnostic_limit: int | None = None,
    category_id: str | None = None,
    smoke: bool = False,
) -> Manifest:
    root = root.resolve()
    snapshot_date = snapshot_date or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    observed_at = _utc_now()
    source = BrowserSource(
        headless=headless,
        request_delay=request_delay,
        retry_count=retry_count,
        timeout_seconds=timeout_seconds,
        diagnostic_limit=diagnostic_limit,
    )
    raw = source.collect(category_id=category_id)
    observations = []
    promotion_map: dict[str, Any] = {}
    promotion_warnings: list[str] = []
    catalog_warnings: list[str] = []
    for category in raw.categories:
        path = " > ".join(category.root.path_names)
        for product in category.products:
            if not str(product.get("N") or "").strip():
                catalog_warnings.append(
                    f"source product {product.get('Id')} has no name; "
                    "used an explicit ID-based placeholder"
                )
            observations.append(normalize_catalog_product(product, observed_at, category.root.category_id, path))
            try:
                for promotion in normalize_promotions(product, observed_at):
                    promotion_map[promotion.promotion_key] = promotion
            except Exception as error:
                promotion_warnings.append(
                    f"promotion normalization warning for product "
                    f"{product.get('Id')}: {error}"
                )
    catalog = merge_product_observations(observations)
    promotions = [promotion_map[key] for key in sorted(promotion_map)]
    snapshot_dir = root / "data/snapshots"
    all_leaves_succeeded = len(raw.categories) == (
        1 if category_id else len(raw.discovery.leaves)
    )
    if (
        diagnostic_limit is not None
        and not smoke
        and diagnostic_limit < len(raw.discovery.leaves)
    ):
        all_leaves_succeeded = False
    metrics = validate_collection(
        catalog,
        snapshot_dir=snapshot_dir,
        snapshot_date=snapshot_date,
        visible_root_count=len(raw.discovery.leaves),
        visible_node_count=raw.discovery.total_nodes,
        all_roots_succeeded=all_leaves_succeeded,
        api_totals_reconciled=all(len(category.products) == category.total for category in raw.categories),
        min_valid_price_percentage=0 if smoke else 95,
        min_prior_overlap_percentage=0 if smoke else 80,
        max_product_drop_percentage=100 if smoke else 25,
    )
    manifest = Manifest(
        snapshot_date=snapshot_date,
        observed_at=observed_at,
        status="healthy",
        store_id=STORE_ID,
        store_name=STORE_NAME,
        store_code=STORE_CODE,
        store_system_name=STORE_SYSTEM_NAME,
        seo_location=SEO_LOCATION,
        market_reference=MARKET_REFERENCE,
        category_tree_id=CATEGORY_TREE_ID,
        leaf_categories=[
            {
                "category_id": leaf.category_id,
                "name": leaf.name,
                "path_names": list(leaf.path_names),
                "path_ids": list(leaf.path_ids),
            }
            for leaf in raw.discovery.leaves
        ],
        successful_leaf_categories=[
            category.root.category_id for category in raw.categories
        ],
        expected_products_from_api_totals=sum(category.total for category in raw.categories),
        raw_product_records=sum(len(category.products) for category in raw.categories),
        unique_products=len(catalog),
        promotions=len(promotions),
        valid_price_percentage=metrics.valid_price_percentage,
        prior_overlap_percentage=metrics.prior_overlap_percentage,
        product_count_change_percentage=metrics.product_count_change_percentage,
        duplicate_key_count=metrics.duplicate_key_count,
        requests=raw.requests,
        retries=raw.retries,
        elapsed_seconds=raw.elapsed_seconds,
        robots_sha256=raw.robots.sha256,
        robots_crawl_delay=raw.robots.crawl_delay,
        store_identity_sha256=raw.store_identity_sha256,
        category_tree_sha256=raw.category_tree_sha256,
        errors=sorted(set(catalog_warnings + promotion_warnings)),
        discovered_category_nodes=raw.discovery.total_nodes,
        discovered_root_nodes=raw.discovery.root_nodes,
        discovered_leaf_nodes=raw.discovery.leaf_nodes,
        rolling_14_day_median_products=metrics.rolling_14_day_median_products,
        adaptive_product_floor=metrics.adaptive_product_floor,
    )

    work_root = root / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="publish-", dir=work_root))
    try:
        stage_snapshots = stage / "snapshots"
        if snapshot_dir.exists():
            shutil.copytree(snapshot_dir, stage_snapshots)
        else:
            stage_snapshots.mkdir(parents=True)
        write_snapshot_bundle(stage_snapshots, snapshot_date, catalog, promotions, manifest)
        stage_docs = stage / "docs"
        docs_dir = root / "docs"
        if docs_dir.exists():
            shutil.copytree(docs_dir, stage_docs)
        else:
            stage_docs.mkdir(parents=True)
        build_reports(stage_snapshots, stage_docs)
        _replace_directories_transactionally(
            [(stage_snapshots, snapshot_dir), (stage_docs, docs_dir)], stage / "backup"
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    LOGGER.info("healthy_snapshot_published", extra={"snapshot_date": snapshot_date, "products": len(catalog)})
    return manifest


def rebuild_reports(root: Path) -> None:
    root = root.resolve()
    snapshot_dir, docs_dir = root / "data/snapshots", root / "docs"
    work_root = root / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="report-", dir=work_root))
    try:
        stage_docs = stage / "docs"
        shutil.copytree(docs_dir, stage_docs)
        build_reports(snapshot_dir, stage_docs)
        _replace_directories_transactionally([(stage_docs, docs_dir)], stage / "backup")
    finally:
        shutil.rmtree(stage, ignore_errors=True)
