#!/usr/bin/env python3
"""Build the unified AI Papers public data contract."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from publisher.build_index import build_unified_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-dir", type=Path, default=PROJECT_ROOT / "data/upstream")
    parser.add_argument(
        "--mh-dir",
        type=Path,
        help="Optional MH snapshot; defaults to data/upstream/mh then data/exports/mental-health",
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "web/public/data")
    parser.add_argument(
        "--start-year",
        type=int,
        default=2023,
        help="Exclude earlier publications from the public index (default: 2023)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data/reports/unified-publish-report.json",
    )
    parser.add_argument(
        "--rss",
        type=Path,
        default=PROJECT_ROOT / "web/public/rss.xml",
    )
    parser.add_argument(
        "--site-url",
        default=os.getenv("SITE_URL", "http://localhost:3000"),
        help="Absolute website URL used in RSS links",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_unified_index(
            upstream_dir=args.upstream_dir,
            mh_dir=args.mh_dir,
            output_dir=args.output_dir,
            report_path=args.report,
            start_year=args.start_year,
            rss_path=args.rss,
            site_url=args.site_url,
        )
    except RuntimeError as exc:
        print(f"build_unified_index failed: {exc}", file=sys.stderr)
        return 1
    counts = report["counts"]
    print(
        f"published {counts['canonical_papers']} canonical papers "
        f"from {counts['input_records']} channel records"
    )
    if report["pending_channels"]:
        print(f"pending channels: {', '.join(report['pending_channels'])}")
    print(f"public data: {args.output_dir}")
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
