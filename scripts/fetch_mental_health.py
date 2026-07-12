#!/usr/bin/env python3
"""Fetch a bounded, free OpenAlex candidate batch for the MH channel."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.mental_health.config import DEFAULT_CONFIG_PATH  # noqa: E402
from src.mental_health.openalex import (  # noqa: E402
    DEFAULT_CANDIDATES_PATH,
    DEFAULT_REPORT_PATH,
    run_fetch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--from-date", default=None, help="YYYY-MM-DD; default comes from theme config (2023-01-01)")
    parser.add_argument("--to-date", default=date.today().isoformat(), help="YYYY-MM-DD; defaults to today")
    parser.add_argument("--limit", type=int, default=20, help="Global candidate cap (default: 20)")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout seconds")
    parser.add_argument("--retries", type=int, default=3, help="Bounded attempts per OpenAlex request")
    parser.add_argument("--dry-run", action="store_true", help="Validate and write a plan without network requests")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        candidates, report = run_fetch(
            config_path=args.config,
            candidates_path=args.output,
            report_path=args.report,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
            dry_run=args.dry_run,
            timeout=args.timeout,
            retries=args.retries,
            contact_email=os.getenv("CONTACT_EMAIL", "anonymous@example.com"),
        )
    except (ValueError, OSError) as exc:
        print(f"mental-health fetch failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"mental-health fetch status={report['status']} candidates={len(candidates)} "
        f"output={args.output} report={args.report}"
    )
    return 0 if report["status"] in {"success", "dry_run", "partial_failure"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
