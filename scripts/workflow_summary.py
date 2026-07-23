from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
manifests = sorted((ROOT / "data/snapshots").glob("????-??-??.manifest.json"))
print("## Gala Freeport–Merrick pipeline")
failure = ROOT / "work/workflow_failure.txt"
if failure.exists():
    print(f"\n- Current run: **failed closed** — {failure.read_text().strip()}")
if not manifests:
    print("\nNo healthy production snapshot is checked in yet. Verify mode completed without network collection.")
else:
    latest = json.loads(manifests[-1].read_text())
    print(f"\n- Status: **{latest.get('status', 'unknown')}**")
    print(f"- Snapshot: `{latest.get('snapshot_date')}` at `{latest.get('observed_at')}`")
    print(f"- Products: **{latest.get('unique_products')}**; promotions: **{latest.get('promotions')}**")
    print(f"- Valid prices: **{latest.get('valid_price_percentage')}%**")
    print(f"- Leaves completed: **{len(latest.get('successful_leaf_categories', []))}/{len(latest.get('leaf_categories', []))}**")
    print(f"- Requests/retries: **{latest.get('requests')}/{latest.get('retries')}**")
    if latest.get("errors"):
        print("- Warnings: " + "; ".join(latest["errors"][:5]))
