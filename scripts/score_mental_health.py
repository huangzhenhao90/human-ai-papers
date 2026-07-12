#!/usr/bin/env python3
"""Score the current MH candidate batch; default mode is a zero-cost dry-run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.mental_health.config import DEFAULT_CONFIG_PATH  # noqa: E402
from src.mental_health.scoring import (  # noqa: E402
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_DIR,
    MissingAPIKeyError,
    ScoringContractError,
    load_candidates,
    run_scoring,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--limit", type=int, default=20, help="Maximum candidates from this input batch")
    parser.add_argument("--batch-size", type=int, default=5)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="Allow paid MiniMax requests; requires MINIMAX_API_KEY")
    mode.add_argument("--dry-run", action="store_true", help="Explicit zero-cost mode (also the default)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        candidates = load_candidates(args.input)
        meta = run_scoring(
            candidates=candidates,
            output_dir=args.output_dir,
            config_path=args.config,
            limit=args.limit,
            batch_size=args.batch_size,
            execute=args.execute,
        )
    except (FileNotFoundError, json.JSONDecodeError, ValueError, MissingAPIKeyError, ScoringContractError) as exc:
        print(f"mental-health scoring failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"mental-health scoring status={meta['status']} dry_run={meta['dry_run']} "
        f"published={meta['totals']['papers_published']} output={args.output_dir}"
    )
    return 0 if meta["status"] in {"success", "dry_run", "empty_input", "partial_failure"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
