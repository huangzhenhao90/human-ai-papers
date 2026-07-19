"""Failure-aware update helpers shared by the CLI and automation workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .git_source import sync_channel
from .io_utils import read_json, write_json
from .normalize_contract import load_channel_snapshot


def _existing_channel_source(output_dir: Path, channel: str) -> dict[str, Any]:
    channel_dir = output_dir / channel
    load_channel_snapshot(channel_dir, channel)
    source_path = channel_dir / "_source.json"
    if source_path.is_file():
        source = read_json(source_path, context=f"read stale channel source={channel}")
        if isinstance(source, dict):
            return source
    return {
        "channel": channel,
        "ref": "existing-snapshot",
        "revision": None,
        "repo": None,
        "generated_at": None,
        "files": {},
    }


def sync_legacy_with_fallback(
    *,
    ob_repo: Path,
    ur_repo: Path,
    ob_ref: str,
    ur_ref: str,
    output_dir: Path,
    initial_failures: list[dict[str, Any]] | None = None,
    initial_stale_channels: list[str] | None = None,
) -> dict[str, Any]:
    """Sync each legacy channel independently and retain the last valid snapshot on failure."""

    sources: dict[str, Any] = {}
    stale_channels: list[str] = list(initial_stale_channels or [])
    failures = list(initial_failures or [])
    for channel, repo, ref in (
        ("ob", ob_repo, ob_ref),
        ("ur", ur_repo, ur_ref),
    ):
        try:
            sources[channel] = sync_channel(repo, ref, channel, output_dir)
        except RuntimeError as exc:
            try:
                sources[channel] = _existing_channel_source(output_dir, channel)
            except RuntimeError as fallback_exc:
                raise RuntimeError(
                    f"sync channel={channel} failed and no valid fallback snapshot exists: "
                    f"{exc}; fallback error: {fallback_exc}"
                ) from exc
            stale_channels.append(channel)
            failures.append(
                {
                    "channel": channel,
                    "stage": "sync_legacy",
                    "error": str(exc),
                    "fallback": "previous_valid_snapshot",
                }
            )

    manifest = {
        "schema_version": 2,
        "channels": sources,
        "stale_channels": sorted(set(stale_channels)),
        "failures": failures,
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def _mental_health_key(record: dict[str, Any]) -> str:
    doi = str(record.get("doi") or "").strip().lower()
    if doi:
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
        return f"doi:{doi}"
    openalex_id = str(record.get("openalex_id") or record.get("id") or "").strip()
    if not openalex_id:
        raise RuntimeError("merge mental-health batch: record has no DOI, OpenAlex ID, or id")
    return f"openalex:{openalex_id.rsplit('/', 1)[-1]}"


def _merge_records(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = {_mental_health_key(record): record for record in existing}
    merged.update({_mental_health_key(record): record for record in incoming})
    return sorted(
        merged.values(),
        key=lambda item: (item.get("date") or "", int(item.get("cited_by") or 0)),
        reverse=True,
    )


def merge_mental_health_batch(*, batch_dir: Path, cumulative_dir: Path) -> dict[str, Any]:
    """Merge a paid, bounded scoring batch into the cumulative public MH snapshot."""

    batch_public = read_json(batch_dir / "papers.json", context="read MH batch papers")
    batch_full = read_json(batch_dir / "papers_full.json", context="read MH batch full papers")
    batch_meta = read_json(batch_dir / "meta.json", context="read MH batch meta")
    if not isinstance(batch_public, list) or not isinstance(batch_full, list):
        raise RuntimeError("merge mental-health batch: batch papers must be arrays")
    if not isinstance(batch_meta, dict) or batch_meta.get("dry_run"):
        raise RuntimeError("merge mental-health batch: only an executed scoring batch may be merged")

    existing_public: list[dict[str, Any]] = []
    existing_full: list[dict[str, Any]] = []
    existing_meta: dict[str, Any] = {}
    if (cumulative_dir / "papers.json").is_file():
        value = read_json(cumulative_dir / "papers.json", context="read cumulative MH papers")
        if not isinstance(value, list):
            raise RuntimeError("merge mental-health batch: cumulative papers.json must be an array")
        existing_public = value
    if (cumulative_dir / "papers_full.json").is_file():
        value = read_json(cumulative_dir / "papers_full.json", context="read cumulative MH full papers")
        if not isinstance(value, list):
            raise RuntimeError("merge mental-health batch: cumulative papers_full.json must be an array")
        existing_full = value
    if (cumulative_dir / "meta.json").is_file():
        value = read_json(cumulative_dir / "meta.json", context="read cumulative MH meta")
        if isinstance(value, dict):
            existing_meta = value

    public = _merge_records(existing_public, batch_public)
    full = _merge_records(existing_full, batch_full)
    public_keys = {_mental_health_key(record) for record in public}
    full_keys = {_mental_health_key(record) for record in full}
    if public_keys != full_keys:
        raise RuntimeError("merge mental-health batch: compact and full snapshots disagree")

    last_batch_totals = dict(batch_meta.get("totals") or {})
    processed_keys = {
        str(key)
        for key in (existing_meta.get("processed_candidate_keys") or [])
        if str(key)
    }
    # Older snapshots predate processed_candidate_keys. Their published records
    # still count as processed so the first automated run does not rescore them.
    processed_keys.update(_mental_health_key(record) for record in existing_full)
    processed_keys.update(
        str(key)
        for key in (batch_meta.get("processed_candidate_keys") or [])
        if str(key)
    )
    cumulative_meta = {
        **batch_meta,
        "scope": "cumulative",
        "processed_candidate_keys": sorted(processed_keys),
        "totals": {
            **last_batch_totals,
            "papers_published": len(public),
        },
        "last_batch": {
            "generated_at": batch_meta.get("generated_at"),
            "status": batch_meta.get("status"),
            "model": batch_meta.get("model"),
            "totals": last_batch_totals,
        },
    }
    write_json(cumulative_dir / "papers.json", public)
    write_json(cumulative_dir / "papers_full.json", full)
    write_json(cumulative_dir / "meta.json", cumulative_meta)
    score_report_path = batch_dir / "score_report.json"
    if score_report_path.is_file():
        write_json(
            cumulative_dir / "score_report.json",
            read_json(score_report_path, context="read MH batch score report"),
        )
    return {
        "previous_papers": len(existing_public),
        "batch_papers": len(batch_public),
        "cumulative_papers": len(public),
        "processed_candidates": len(processed_keys),
        "status": batch_meta.get("status"),
    }
