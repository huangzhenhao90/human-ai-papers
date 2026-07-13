#!/usr/bin/env python3
"""Validate every cross-file release invariant before deployment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from publisher.validate_release import validate_release


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "web/public/data")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "data/reports/unified-publish-report.json")
    parser.add_argument("--rss", type=Path, default=PROJECT_ROOT / "web/public/rss.xml")
    parser.add_argument("--allow-pending", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate_release(
            output_dir=args.output_dir,
            report_path=args.report,
            rss_path=args.rss,
            require_all_channels=not args.allow_pending,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
