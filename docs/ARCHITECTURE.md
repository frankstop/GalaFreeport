# Architecture

## Fixed market boundary

The adapter accepts only Gala Supermarkets store `6`,
`GF_Freeport_Merrick_111`, at 111 West Merrick Road. Store identity is
re-verified from the public store and footer responses on every run.

## Raw → derived → published

### Raw evidence

`browser_source.py` fetches and evaluates `robots.txt`, then opens one clean
Playwright Chromium context at the exact Freeport–Merrick URL. The browser
router blocks customer, account, cart, checkout, address, loyalty, coupon, and
order paths, plus image/font/media downloads.

The source fetches only the required same-origin JSON:

- `/api/multistore/StoresDialogJSON`
- `/api/Common/FooterJSON`
- `/api/AjaxFilter/GetCategoryTreeJSON?filterMode=00000000`
- `/api/AjaxFilter/JsonProductsList?pageNumber=N&filterMode=00000000`

`discovery.py` validates the `Id`/`N`/`List` tree and selects every leaf
dynamically. Each product call uses the observed two-filter JSON body. The
adapter decodes `productsJson`, validates the pager, detects repeated pages and
IDs, rejects empty intermediate pages or inconsistent totals, and reconciles
each leaf exactly to `productsCount`.

`parsers.py` retains `Id`, `SPId`, and `SKU` separately, scopes the stable key
to store 6, unions overlapping category memberships, preserves raw price
display evidence, and separates sale, multi-buy, and BOGO observations from
catalog regular prices.

`storage.py` writes deterministic JSON and gzip (`mtime=0`). The pipeline builds
the next snapshots and Pages tree in staging and replaces them transactionally
only after collection, validation, and report generation succeed.

### Derived research

`analysis.py` reads only checked-in snapshots. It calculates adjacent-day and
weekly comparisons, first additions, returns, gaps, assortment churn,
regular-price movements, promotion transitions, and conservative robust
anomaly flags. Missing observations remain missing.

`catalog_history.py` constructs the complete union catalog with one slot per
calendar day. `price_changes_page.py` uses complete date shards. Business
metrics are never recalculated in browser JavaScript.

### Published views

`report.py` writes accessible static HTML and stable JSON under `docs/data/`.
The catalog and price-change explorers provide full filtering, pagination,
direct item evidence, and CSV/JSON export.

## Failure rules

- Policy denial, CAPTCHA/authentication, required `401`/`403`, wrong store, or
  contract ambiguity: publish nothing.
- Missing leaves, page loops, duplicate page IDs, or count mismatch: publish
  nothing.
- Validation, report, test, or checker failure: retain the prior healthy state.
- Same-day healthy rerun: replace all three channels and derived reports
  together.
- Offline report rebuild: never mutate raw snapshots.

## Dependency boundary

The standard library handles models, JSON, gzip, validation, analysis, and HTML
generation. Playwright is the only runtime dependency.
