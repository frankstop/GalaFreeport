from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any

SCHEMA_VERSION = "1.0"
RETAILER = "Gala Supermarkets"
STORE_NAME = "Freeport Merrick"
STORE_ID = 6
STORE_CODE = "GF_Freeport_Merrick_111"
STORE_SYSTEM_NAME = "Freeport_Merrick_111"
SEO_LOCATION = "Freeport-Merrick"
CATEGORY_TREE_ID = "1"
MARKET_REFERENCE = "111 West Merrick Road, Freeport, NY 11520"
STOREFRONT_URL = "https://galasupermarkets.com/Freeport-Merrick"
PRICE_SCOPE = "public_online_catalog"
CURRENCY = "USD"


def finite_nonnegative(value: Any) -> float | None:
    """Return a finite non-negative float while preserving missing values."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number >= 0 else None


@dataclass(frozen=True, slots=True)
class CategoryLeaf:
    category_id: str
    name: str
    path_names: tuple[str, ...]
    path_ids: tuple[str, ...]


# The downstream series originally called a collected category a root. Keep this
# import alias so older report code remains source compatible while this adapter
# explicitly discovers and crawls leaves.
CategoryRoot = CategoryLeaf


@dataclass(slots=True)
class CatalogObservation:
    product_key: str
    retailer_product_id: str
    catalog_product_id: str | None
    branch_product_id: str | None
    source_id: str
    sp_id: str | None
    sku: str | None
    name: str
    description: str | None
    brand: str | None
    regular_price: float | None
    current_price: float | None
    display_price: str | None
    original_display_price: str | None
    currency: str
    weight: str | float | None
    unit_of_measure: str | None
    unit_resolution: str | float | None
    is_weighable: bool | None
    is_out_of_stock: bool | None
    is_active: bool | None
    is_visible: bool | None
    is_ebt_eligible: bool | None
    category_paths: list[str]
    source_category_ids: list[str]
    image_url: str | None
    promotion_ids: list[str]
    observed_at: str
    retailer: str = RETAILER
    store_name: str = STORE_NAME
    store_id: int = STORE_ID
    store_code: str = STORE_CODE
    market_reference: str = MARKET_REFERENCE
    price_scope: str = PRICE_SCOPE
    source_url: str = STOREFRONT_URL
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["category_paths"] = sorted(set(self.category_paths))
        value["source_category_ids"] = sorted(set(self.source_category_ids))
        value["promotion_ids"] = sorted(set(self.promotion_ids))
        return value


@dataclass(slots=True)
class PromotionObservation:
    promotion_key: str
    promotion_id: str
    product_key: str
    promotion_type: str
    description: str | None
    display_name: str | None
    promotion_tag: str | None
    valid_from: str | None
    valid_to: str | None
    is_coupon: bool | None
    limit: float | int | None
    first_level: dict[str, Any] | None
    levels: list[dict[str, Any]]
    raw_offer_structure: dict[str, Any]
    derived_effective_unit_price: float | None
    derivation_basis: str | None
    observed_at: str
    store_id: int = STORE_ID
    store_code: str = STORE_CODE
    price_scope: str = PRICE_SCOPE
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Manifest:
    snapshot_date: str
    observed_at: str
    status: str
    store_id: int
    store_name: str
    store_code: str
    store_system_name: str
    seo_location: str
    market_reference: str
    category_tree_id: str
    leaf_categories: list[dict[str, Any]]
    successful_leaf_categories: list[str]
    expected_products_from_api_totals: int
    raw_product_records: int
    unique_products: int
    promotions: int
    valid_price_percentage: float
    prior_overlap_percentage: float | None
    product_count_change_percentage: float | None
    duplicate_key_count: int
    requests: int
    retries: int
    elapsed_seconds: float
    robots_sha256: str
    robots_crawl_delay: float
    store_identity_sha256: str
    category_tree_sha256: str
    errors: list[str] = field(default_factory=list)
    discovered_category_nodes: int = 0
    discovered_root_nodes: int = 0
    discovered_leaf_nodes: int = 0
    rolling_14_day_median_products: float | None = None
    adaptive_product_floor: int | None = None
    source_contract_version: str = "my-cloud-grocer-v1"
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
