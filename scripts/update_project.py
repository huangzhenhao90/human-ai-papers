#!/usr/bin/env python3
"""Run the complete failure-aware update, build, and release-validation chain."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from publisher.build_index import build_unified_index
from publisher.io_utils import write_json
from publisher.update_pipeline import merge_mental_health_batch, sync_legacy_with_fallback
from publisher.validate_release import validate_release
from src.mental_health.openalex import candidate_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ob", type=Path, default=PROJECT_ROOT.parent / "ob-ai-papers")
    parser.add_argument("--ur", type=Path, default=PROJECT_ROOT.parent / "ur-ai-papers")
    parser.add_argument("--ob-ref", default="origin/main")
    parser.add_argument("--ur-ref", default="origin/main")
    parser.add_argument("--skip-sync", action="store_true", help="Build from existing upstream snapshots")
    parser.add_argument("--skip-fetch-remotes", action="store_true", help="Do not refresh origin before snapshotting")
    parser.add_argument("--mh-mode", choices=("skip", "fetch", "dry-run", "execute"), default="skip")
    parser.add_argument("--mh-limit", type=int, default=12, help="Bounded MH candidate/scoring cap")
    parser.add_argument("--mh-scan-limit", type=int, default=120, help="Free MH recall scan cap before excluding processed candidates")
    parser.add_argument("--mh-batch-size", type=int, default=4)
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--site-url", default=os.getenv("SITE_URL", "http://localhost:3300"))
    parser.add_argument("--allow-pending", action="store_true")
    return parser.parse_args()


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{output}")
    return output


def _fetch_remote(channel: str, repo: Path) -> dict[str, Any] | None:
    try:
        _run(["git", "-C", str(repo), "fetch", "--prune", "origin"])
    except RuntimeError as exc:
        return {"channel": channel, "stage": "git_fetch", "error": str(exc), "fallback": "cached_git_ref"}
    return None


def _update_mental_health(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.mh_mode == "skip":
        return None
    with tempfile.TemporaryDirectory(prefix="human-ai-papers-mh-") as temporary:
        temp = Path(temporary)
        candidates = temp / "candidates.json"
        fetch_report = temp / "fetch-report.json"
        fetch_command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts/fetch_mental_health.py"),
            "--output", str(candidates),
            "--report", str(fetch_report),
            "--limit", str(args.mh_scan_limit),
        ]
        if args.mh_mode == "dry-run":
            fetch_command.append("--dry-run")
        _run(fetch_command)
        if args.mh_mode in {"fetch", "dry-run"}:
            return {"mode": args.mh_mode, "fetch_report": json.loads(fetch_report.read_text())}

        fetched = json.loads(candidates.read_text())
        cumulative_dir = PROJECT_ROOT / "data/exports/mental-health"
        processed_keys: set[str] = set()
        meta_path = cumulative_dir / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text())
            processed_keys.update(str(key) for key in meta.get("processed_candidate_keys") or [])
        full_path = cumulative_dir / "papers_full.json"
        if full_path.is_file():
            processed_keys.update(candidate_key(record) for record in json.loads(full_path.read_text()))
        selected = [item for item in fetched if candidate_key(item) not in processed_keys][: args.mh_limit]
        write_json(candidates, selected)

        batch_dir = temp / "scored"
        _run([
            sys.executable,
            str(PROJECT_ROOT / "scripts/score_mental_health.py"),
            "--input", str(candidates),
            "--output-dir", str(batch_dir),
            "--execute",
            "--limit", str(args.mh_limit),
            "--batch-size", str(args.mh_batch_size),
        ])
        merged = merge_mental_health_batch(
            batch_dir=batch_dir,
            cumulative_dir=PROJECT_ROOT / "data/exports/mental-health",
        )
        return {
            "mode": "execute",
            "selection": {
                "fetched": len(fetched),
                "already_processed": len(fetched) - len([item for item in fetched if candidate_key(item) not in processed_keys]),
                "selected_for_scoring": len(selected),
                "scoring_limit": args.mh_limit,
                "scan_limit": args.mh_scan_limit,
            },
            "merge": merged,
        }


def main() -> int:
    args = parse_args()
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    failures: list[dict[str, Any]] = []
    stale_channels: list[str] = []
    upstream_dir = PROJECT_ROOT / "data/upstream"

    try:
        if not args.skip_sync:
            if not args.skip_fetch_remotes:
                for channel, repo in (("ob", args.ob), ("ur", args.ur)):
                    failure = _fetch_remote(channel, repo)
                    if failure:
                        failures.append(failure)
                        stale_channels.append(channel)
            manifest = sync_legacy_with_fallback(
                ob_repo=args.ob,
                ur_repo=args.ur,
                ob_ref=args.ob_ref,
                ur_ref=args.ur_ref,
                output_dir=upstream_dir,
                initial_failures=failures,
                initial_stale_channels=stale_channels,
            )
            failures = list(manifest["failures"])
            stale_channels = list(manifest["stale_channels"])

        mh_result: dict[str, Any] | None = None
        try:
            mh_result = _update_mental_health(args)
        except RuntimeError as exc:
            mh_snapshot = PROJECT_ROOT / "data/exports/mental-health/papers.json"
            if not mh_snapshot.is_file():
                raise
            stale_channels.append("mh")
            failures.append({"channel": "mh", "stage": "mental_health_update", "error": str(exc), "fallback": "previous_valid_snapshot"})

        report = build_unified_index(
            upstream_dir=upstream_dir,
            mh_dir=PROJECT_ROOT / "data/exports/mental-health",
            registry_path=PROJECT_ROOT / "config/channels.yaml",
            output_dir=PROJECT_ROOT / "web/public/data",
            report_path=PROJECT_ROOT / "data/reports/unified-publish-report.json",
            start_year=args.start_year,
            rss_path=PROJECT_ROOT / "web/public/rss.xml",
            site_url=args.site_url,
            stale_channels=stale_channels,
            failures=failures,
        )
        validation = validate_release(
            output_dir=PROJECT_ROOT / "web/public/data",
            report_path=PROJECT_ROOT / "data/reports/unified-publish-report.json",
            rss_path=PROJECT_ROOT / "web/public/rss.xml",
            require_all_channels=not args.allow_pending,
        )
        run_report = {
            "schema_version": 1,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "partial" if failures or stale_channels else "ok",
            "mh_mode": args.mh_mode,
            "mh_result": mh_result,
            "failures": failures,
            "stale_channels": sorted(set(stale_channels)),
            "publish_counts": report["counts"],
            "validation": validation,
        }
        write_json(PROJECT_ROOT / "data/reports/update-run.json", run_report)
        print(json.dumps(run_report, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"update_project failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
