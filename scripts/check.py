from __future__ import annotations

import compileall
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gala_freeport.report import build_reports
from gala_freeport.storage import read_jsonl_gz, snapshot_files


REQUIRED = [
    "README.md", "LICENSE", "pyproject.toml", ".github/workflows/daily_crawl.yml",
    "docs/index.html", "docs/daily-report.html", "docs/weekly-report.html", "docs/price-changes.html", "docs/catalog.html", "docs/catalog-history.html", "docs/assets/analytics.js",
    "docs/METHODOLOGY.md", "docs/METHODOLOGY.html", "docs/ARCHITECTURE.md", "docs/DATA_DICTIONARY.md",
]


def main() -> int:
    errors: list[str] = []
    if not compileall.compile_dir(ROOT / "gala_freeport", quiet=1):
        errors.append("Python compilation failed")
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f"missing required file: {relative}")
    snapshot_dir = ROOT / "data/snapshots"
    catalog_files = snapshot_files(snapshot_dir, "catalog")
    for path in catalog_files:
        rows = read_jsonl_gz(path)
        keys = [row.get("product_key") for row in rows]
        if len(keys) != len(set(keys)):
            errors.append(f"duplicate product keys in {path.name}")
        if not (snapshot_dir / f"{path.name[:10]}.promotions.jsonl.gz").exists():
            errors.append(f"missing promotion channel for {path.name[:10]}")
        manifest = snapshot_dir / f"{path.name[:10]}.manifest.json"
        if not manifest.exists() or json.loads(manifest.read_text()).get("status") != "healthy":
            errors.append(f"missing healthy manifest for {path.name[:10]}")
    if catalog_files:
        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary) / "docs"
            import shutil
            shutil.copytree(ROOT / "docs", docs)
            build_reports(snapshot_dir, docs)
    for contract in ("docs/data/daily-summary.json", "docs/data/weekly-summary.json", "docs/data/price-changes/index.json"):
        path = ROOT / contract
        if path.exists():
            json.loads(path.read_text())
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"check: ok ({len(catalog_files)} healthy catalog snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
