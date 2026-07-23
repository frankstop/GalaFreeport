from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .pipeline import rebuild_reports, run_pipeline


def _source_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository or isolated smoke root")
    parser.add_argument("--snapshot-date", help="New York snapshot date (YYYY-MM-DD)")
    parser.add_argument("--headed", action="store_true", help="Show Chromium instead of running headless")
    parser.add_argument("--request-delay", type=float, default=1.5, help="Requested minimum delay; robots.txt may raise it")
    parser.add_argument("--retry-count", type=int, default=2, help="Bounded request retry count")
    parser.add_argument("--timeout", type=float, default=45.0, help="Browser timeout in seconds")
    parser.add_argument("--diagnostic-limit", type=int, help="Limit leaves for diagnostics; production validation will reject partial data")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m gala_freeport")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Collect, validate, analyze, and publish one daily snapshot")
    _source_flags(run)
    run.add_argument("--verbose", action="store_true")
    report = subparsers.add_parser("report", help="Rebuild static reports without network access")
    report.add_argument("--root", type=Path, default=Path.cwd())
    smoke = subparsers.add_parser("smoke", help="Collect one visible category into an isolated temporary root")
    _source_flags(smoke)
    smoke.add_argument("--category-id", required=True)
    smoke.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "verbose", False):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.command == "report":
        rebuild_reports(args.root)
        return 0
    if args.command == "smoke" and args.root.resolve() == Path.cwd().resolve():
        raise SystemExit("smoke --root must be an isolated directory, never the production repository")
    manifest = run_pipeline(
        args.root,
        snapshot_date=args.snapshot_date,
        headless=not args.headed,
        request_delay=args.request_delay,
        retry_count=args.retry_count,
        timeout_seconds=args.timeout,
        diagnostic_limit=args.diagnostic_limit,
        category_id=getattr(args, "category_id", None),
        smoke=args.command == "smoke",
    )
    print(json.dumps(manifest.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
