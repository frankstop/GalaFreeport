# Data dictionary

Missing values are JSON `null`, never zero substitutes.

## Catalog observation

| Field | Meaning |
|---|---|
| `product_key` | Stable `gala:store:6:product:{Id}` key. |
| `source_id`, `retailer_product_id` | Source `Id`; primary listing identity. |
| `sp_id`, `catalog_product_id` | Source `SPId`; retained without UPC claims. |
| `sku` | Source `SKU`; retained as source data, not labeled UPC. |
| `name`, `description`, `brand` | Public text; brand is null when not exposed. |
| `regular_price` | Normalized public online regular-price observation. |
| `current_price` | Numeric current-price evidence from `P_v`/`P`. |
| `display_price`, `original_display_price` | Raw public `P` and `O` strings. |
| `is_weighable`, `unit_of_measure` | Preserved weight/unit semantics. |
| `category_paths`, `source_category_ids` | Sorted union across leaf overlap. |
| `promotion_ids` | Separate normalized promotion references. |
| `store_id`, `store_code`, `market_reference` | Fixed verified market identity. |
| `observed_at`, `source_url`, `schema_version` | Provenance and contract fields. |

## Promotion observation

| Field | Meaning |
|---|---|
| `promotion_key`, `promotion_id`, `product_key` | Stable promotion identity. |
| `promotion_type` | `sale`, `multi_buy`, or `bogo`. |
| `raw_offer_structure` | Sanitized source fields supporting the observation. |
| `derived_effective_unit_price` | Conservative derivation or null. |
| `derivation_basis` | Human-readable evidence for a derivation. |
| `valid_from`, `valid_to` | Source BOGO interval when exposed. |

## Manifest

The manifest records the exact store identity, category tree, every discovered
and successful leaf, declared and collected counts, unique products,
promotions, price validity, longitudinal gates, request/retry counts, elapsed
time, robots hash/delay, store/category contract hashes, warnings, and schema
versions.

## Published contracts

`daily-summary.json` and `weekly-summary.json` contain snapshot health,
assortment, regular-price, promotion, and anomaly summaries.

`price-changes/index.json` describes all adjacent healthy comparisons; each
date shard contains every comparable regular-price movement.

`catalog-history/index.json` contains the complete browse index. Deterministic
two-character shards contain every item and an explicit observation slot for
each calendar day, including null gaps.
