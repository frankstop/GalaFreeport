# Gala Freeport–Merrick Catalog Research

Daily longitudinal research on the anonymous public online catalog for Gala
Supermarkets’ **Freeport Merrick** store at 111 West Merrick Road, Freeport,
NY 11520.

This repository observes the public digital storefront. It does not claim that
online prices are physical shelf prices, and it is independent of Gala
Supermarkets and My Cloud Grocer.

## Status

The repository is awaiting its first reviewed healthy production crawl. The
first complete crawl is the honest baseline; comparisons begin only with a
second healthy observation.

- Pages: <https://frankstop.github.io/GalaFreeport/>
- Daily report: <https://frankstop.github.io/GalaFreeport/daily-report.html>
- Weekly report: <https://frankstop.github.io/GalaFreeport/weekly-report.html>
- Price changes: <https://frankstop.github.io/GalaFreeport/price-changes.html>
- Catalog: <https://frankstop.github.io/GalaFreeport/catalog.html>

## Fixed identity boundary

Every production run must verify:

- store ID `6`
- store code `GF_Freeport_Merrick_111`
- system name `Freeport_Merrick_111`
- SEO location `Freeport-Merrick`
- category tree `1`
- address `111 West Merrick Road, Freeport, NY 11520`

Any mismatch fails closed and publishes nothing.

## Architecture

1. **Raw evidence** — one clean, non-persistent Playwright Chromium context
   verifies the store, discovers all live category leaves, and calls the
   anonymous My Cloud Grocer product endpoint serially. Each leaf must reconcile
   exactly to `productsCount`.
2. **Derived research** — tested Python calculates daily and weekly changes,
   gaps, returns, churn, regular-price movements, promotion transitions,
   conservative anomaly flags, catalog history, and date-sharded price changes.
3. **Published views** — static GitHub Pages reads stable JSON under
   `docs/data/`. Browser JavaScript filters and formats already-derived fields;
   it does not calculate business metrics.

Healthy dates produce:

```text
data/snapshots/YYYY-MM-DD.catalog.jsonl.gz
data/snapshots/YYYY-MM-DD.promotions.jsonl.gz
data/snapshots/YYYY-MM-DD.manifest.json
```

The stable product key is `gala:store:6:product:{Id}`. Source `Id`, `SPId`, and
`SKU` are retained independently. `SKU` is not labeled as a UPC.

See [Architecture](docs/ARCHITECTURE.md),
[Data dictionary](docs/DATA_DICTIONARY.md), and
[Methodology](docs/METHODOLOGY.md).

## Commands

Requires Python 3.11+.

```bash
python -m pip install -e .
python -m playwright install chromium
python -m gala_freeport report
python -m gala_freeport smoke --category-id 11042 --root /tmp/gala-freeport-smoke
python -m gala_freeport run --verbose
python -m unittest discover -v
python scripts/check.py
```

`smoke` requires an isolated root and can never write the production snapshot
directory. `--diagnostic-limit` deliberately fails production validation if it
would publish a partial crawl.

## Integrity gates

A production run is rejected unless:

- the current `robots.txt` permits every required path;
- the exact Freeport–Merrick identity is verified;
- the complete category tree is discovered;
- every leaf completes with exact totals and terminating pagination;
- normalized keys are unique;
- at least 95% of observations have a finite positive normalized regular price.

After baseline, the run also requires at least 80% prior-key overlap, no
unexplained product-count drop over 25%, no suspicious category-tree
contraction, and a catalog count at least 75% of the rolling median of up to 14
prior healthy observations.

## Responsible-access boundary

The collector uses only anonymous first-party public catalog routes allowed by
the current `robots.txt`. It uses one context, one serial rate limiter, bounded
retries, and no image downloads.

It never signs in, creates an account, submits an address, uses loyalty or
customer data, searches personalized records, uses coupons, adds to a cart,
checks out, persists browser state, bypasses CAPTCHAs, uses stealth plugins, or
uses proxies. Customer/account/cart/checkout routes are blocked. Policy denial,
authentication, CAPTCHA, repeated `403`, contract ambiguity, or incomplete
pagination fails closed.

## Automation

GitHub Actions runs the collection at **5:17 AM America/New_York** every day,
including daylight-saving transitions. Manual dispatch supports `verify` and
`collect`. Tests and `scripts/check.py` always run, a useful step summary is
always written, and only a healthy raw-and-derived bundle is committed.

GitHub Pages serves `main/docs`.

## License

MIT. Source storefront content remains attributable to its respective owners.
