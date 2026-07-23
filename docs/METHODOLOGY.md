# Methodology

## Scope

The research observes anonymously visible products, online regular-price
evidence, category memberships, exposed product flags, and public promotions
for Gala Supermarkets Freeport Merrick. Online values are not asserted as
physical shelf prices.

## Collection and matching

One clean, non-persistent Chromium context verifies store 6 and discovers every
current category leaf. Leaf results are paginated serially and reconciled to
their declared totals. Overlap across leaves is deduplicated with
`gala:store:6:product:{Id}`, while category memberships are unioned.

`Id`, `SPId`, and `SKU` are retained independently. The project does not claim
that `SKU` is a UPC.

## Prices and promotions

`P_v` and the public display string `P` are preserved as current-price
evidence. When an explicit original display `O` accompanies a sale or
quantity-for-price offer, its numeric value is the regular-price observation.
Otherwise the current numeric price is the regular-price observation. Missing
prices remain null.

Sale, quantity-for-price, and BOGO evidence is stored separately. A quantity
offer derives an effective unit price only from explicit source quantity and
total fields. BOGO derives an effective unit price only when buy/get quantities
and the free-item structure are explicit. Derived values never replace the
regular-price field.

## Missingness and history

Absence means only “not observed in that healthy public result.” It is not
deletion, zero, or confirmed out-of-stock status. Histories keep explicit null
gaps and never interpolate or forward-fill.

The first complete reviewed crawl is the baseline. Comparisons start with the
second healthy observation. Additions have never appeared before; returns were
seen earlier but were absent from the immediately prior healthy observation.

## Validation and anomalies

Every leaf must reconcile exactly. At least 95% of catalog observations must
have finite positive regular prices. Later runs require 80% overlap, reject
unexplained drops over 25%, reject major tree contraction, and enforce 75% of
the rolling median of up to 14 prior healthy catalog counts.

An anomaly is descriptive, not predictive: an absolute regular-price movement
of at least 20% and an absolute robust median-absolute-deviation z-score of at
least 3.5.

## Responsible access

The collector evaluates `robots.txt` before opening Chromium and applies the
greater of its configured or policy delay to all required catalog requests.
It blocks customer/account/cart/checkout and related paths and never
authenticates, submits addresses, persists profiles, automates carts, uses
stealth, solves CAPTCHAs, or rotates proxies.

## Limitations

The research reflects only the anonymous public online response at observation
time. It cannot establish shelf price, in-store inventory, transaction
eligibility, promotion eligibility for a specific shopper, or why an item is
absent. The source schema, merchandising, category tree, and access policy may
change.
