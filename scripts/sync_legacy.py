#!/usr/bin/env python3
"""Snapshot OB and UR public JSON from formal Git revisions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from publisher.git_source import sync_legacy_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ob", type=Path, default=PROJECT_ROOT.parent / "ob-ai-papers")
    parser.add_argument("--ur", type=Path, default=PROJECT_ROOT.parent / "ur-ai-papers")
    parser.add_argument("--ob-ref", default="origin/main")
    parser.add_argument("--ur-ref", default="origin/main")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/upstream")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = sync_legacy_sources(
            ob_repo=args.ob,
            ur_repo=args.ur,
            ob_ref=args.ob_ref,
            ur_ref=args.ur_ref,
            output_dir=args.output_dir,
        )
    except RuntimeError as exc:
        print(f"sync_legacy failed: {exc}", file=sys.stderr)
        return 1
    for channel, source in manifest["channels"].items():
        print(f"{channel}: {source['revision']} ({source['generated_at']})")
    print(f"snapshots: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
