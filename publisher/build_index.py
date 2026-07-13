"""Build deterministic public artifacts from normalized channel snapshots."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .build_rss import build_rss_xml
from .channel_registry import default_registry_path, load_channel_registry, resolve_channel_data_dir
from .io_utils import json_bytes, read_json, replace_json_directory, write_bytes, write_json
from .merge_channels import merge_channel_records_with_diagnostics
from .normalize_contract import ChannelSnapshot, load_channel_snapshot


LIST_FIELDS = (
    "id",
    "doi",
    "title",
    "title_zh",
    "date",
    "year",
    "journal",
    "authors",
    "channels",
    "channel_profiles",
    "source_refs",
    "ai_type_tags",
    "cited_by",
    "url",
    "pdf_url",
    "volume",
    "issue",
)
DETAIL_FIELDS = (
    *LIST_FIELDS,
    "arxiv_id",
    "abstract",
    "authors_full",
    "unified_ingested_at",
)


def _select_fields(paper: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: paper.get(field) for field in fields}


def _facet_counts(papers: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    years: Counter[str] = Counter()
    journals: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    ai_types: Counter[str] = Counter()
    channels: Counter[str] = Counter()
    for paper in papers:
        if paper.get("year") not in (None, ""):
            years[str(paper["year"])] += 1
        if paper.get("journal"):
            journals[str(paper["journal"])] += 1
        for channel in paper["channels"]:
            channels[channel] += 1
        for tag in set(paper.get("ai_type_tags") or []):
            ai_types[str(tag)] += 1
        paper_topics = {
            str(tag)
            for profile in paper["channel_profiles"].values()
            for tag in (profile.get("topic_tags") or [])
        }
        topics.update(paper_topics)
    return {
        "years": dict(sorted(years.items())),
        "journals": dict(sorted(journals.items())),
        "topic_tags": dict(sorted(topics.items())),
        "ai_type_tags": dict(sorted(ai_types.items())),
        "channels": dict(sorted(channels.items())),
    }


def _upstream_generated_at(snapshots: list[ChannelSnapshot]) -> str:
    candidates = [
        str(snapshot.meta.get("generated_at") or snapshot.source.get("generated_at") or "")
        for snapshot in snapshots
    ]
    return max((value for value in candidates if value), default="1970-01-01T00:00:00Z")


def _build_timestamp(output_dir: Path, data_version: str) -> str:
    """Keep identical builds byte-stable while timestamping changed content."""

    meta_path = output_dir / "meta.json"
    if meta_path.exists():
        try:
            existing = read_json(meta_path, context="reuse build timestamp")
        except RuntimeError:
            existing = None
        if isinstance(existing, dict) and existing.get("data_version") == data_version:
            previous = existing.get("built_at") or existing.get("generated_at")
            if previous:
                return str(previous)
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_year(record: dict[str, Any]) -> int | None:
    for value in (record.get("year"), record.get("date")):
        match = re.search(r"\d{4}", str(value or ""))
        if match:
            return int(match.group(0))
    return None


def _assign_first_seen(
    papers: list[dict[str, Any]], output_dir: Path, built_at: str
) -> None:
    for paper in papers:
        detail_path = output_dir / "papers" / f"{paper['id']}.json"
        previous: Any = None
        if detail_path.exists():
            try:
                previous = read_json(detail_path, context="reuse unified first-seen timestamp")
            except RuntimeError:
                previous = None
        if isinstance(previous, dict) and previous.get("unified_ingested_at"):
            paper["unified_ingested_at"] = str(previous["unified_ingested_at"])
        else:
            paper["unified_ingested_at"] = built_at


def _channel_coverage(
    snapshot: ChannelSnapshot, *, included_records: int, canonical_memberships: int
) -> dict[str, Any]:
    journals = snapshot.meta.get("journals")
    if not isinstance(journals, list):
        journals = []
    return {
        "status": "ready",
        "upstream_published_records": snapshot.diagnostics["normalized"],
        "included_records": included_records,
        "canonical_memberships": canonical_memberships,
        "input_compact": snapshot.diagnostics["input_compact"],
        "input_full": snapshot.diagnostics["input_full"],
        "source_revision": snapshot.source.get("revision"),
        "source_generated_at": snapshot.meta.get("generated_at")
        or snapshot.source.get("generated_at"),
        "upstream_totals": snapshot.meta.get("totals", {}),
        "upstream_status": snapshot.meta.get("status"),
        "dry_run": snapshot.meta.get("dry_run"),
        "model": snapshot.meta.get("model"),
        "thresholds": snapshot.meta.get("thresholds", {}),
        "facets": snapshot.meta.get("facets", {}),
        "source_candidates": snapshot.meta.get("source_candidates", {}),
        "sources": journals,
    }


def build_unified_index(
    *,
    upstream_dir: Path,
    output_dir: Path,
    report_path: Path,
    mh_dir: Path | None = None,
    registry_path: Path | None = None,
    start_year: int = 2023,
    rss_path: Path | None = None,
    site_url: str = "http://localhost:3300",
    stale_channels: list[str] | None = None,
    failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build all public JSON plus an auditable canonical-key report."""

    definitions = load_channel_registry(registry_path or default_registry_path())
    project_root = Path(__file__).resolve().parents[1]
    stale = sorted(set(stale_channels or []))
    update_failures = list(failures or [])
    snapshots: list[ChannelSnapshot] = []
    pending_channels: list[str] = []
    for definition in definitions:
        upstream_override = upstream_dir / definition.id
        if definition.id == "mh" and mh_dir is not None:
            channel_dir = mh_dir
        elif definition.id == "mh" and (upstream_override / "papers.json").is_file():
            channel_dir = upstream_override
        else:
            channel_dir = resolve_channel_data_dir(
                definition, project_root=project_root, upstream_dir=upstream_dir
            )
        if channel_dir is None or not (channel_dir / "papers.json").is_file():
            if definition.required:
                raise RuntimeError(
                    f"build unified index: required channel={definition.id} has no snapshot at {channel_dir}"
                )
            pending_channels.append(definition.id)
            continue
        try:
            snapshots.append(load_channel_snapshot(channel_dir, definition.id))
        except RuntimeError as exc:
            if not definition.required:
                raise RuntimeError(
                    f"build unified index: optional channel={definition.id} is invalid: {exc}"
                ) from exc
            raise RuntimeError(
                f"build unified index: required channel={definition.id} could not be loaded; "
                f"run scripts/sync_legacy.py first: {exc}"
            ) from exc

    source_records = [record for snapshot in snapshots for record in snapshot.records]
    excluded_before_start_year = sorted(
        (
            {
                "channel": str(record["_channel"]),
                "legacy_id": record.get("id"),
                "year": _record_year(record),
            }
            for record in source_records
            if _record_year(record) is not None and _record_year(record) < start_year
        ),
        key=lambda item: (item["year"], item["channel"], str(item["legacy_id"])),
    )
    all_records = [
        record
        for record in source_records
        if _record_year(record) is None or _record_year(record) >= start_year
    ]
    merged, conflicts = merge_channel_records_with_diagnostics(all_records)
    public_papers = [_select_fields(paper, LIST_FIELDS) for paper in merged]
    version_payload = {
        "start_year": start_year,
        "papers": [
            _select_fields(
                paper,
                (field for field in DETAIL_FIELDS if field != "unified_ingested_at"),
            )
            for paper in merged
        ],
        "sources": {
            snapshot.channel: {
                "revision": snapshot.source.get("revision"),
                "generated_at": snapshot.meta.get("generated_at")
                or snapshot.source.get("generated_at"),
                "status": snapshot.meta.get("status"),
                "dry_run": snapshot.meta.get("dry_run"),
                "model": snapshot.meta.get("model"),
            }
            for snapshot in snapshots
        },
        "pending_channels": pending_channels,
        "stale_channels": stale,
        "failures": update_failures,
        "channel_registry": [definition.public_dict() for definition in definitions],
    }
    data_version = hashlib.sha256(json_bytes(version_payload)).hexdigest()[:16]
    upstream_generated_at = _upstream_generated_at(snapshots)
    built_at = _build_timestamp(output_dir, data_version)
    _assign_first_seen(merged, output_dir, built_at)
    details = {paper["id"]: _select_fields(paper, DETAIL_FIELDS) for paper in merged}

    channel_counts = Counter(
        channel for paper in public_papers for channel in paper["channels"]
    )
    meta = {
        "generated_at": built_at,
        "built_at": built_at,
        "upstream_generated_at": upstream_generated_at,
        "data_version": data_version,
        "start_year": start_year,
        "totals": {
            "papers": len(public_papers),
            "source_records": len(source_records),
            "included_records": len(all_records),
            "excluded_before_start_year": len(excluded_before_start_year),
            "cross_channel_papers": sum(len(paper["channels"]) > 1 for paper in public_papers),
        },
        "channels": {
            definition.id: {
                **definition.public_dict(),
                "papers": channel_counts.get(definition.id, 0),
                "status": "pending" if definition.id in pending_channels else "stale" if definition.id in stale else "ready",
            }
            for definition in definitions
        },
        "facets": _facet_counts(public_papers),
    }
    coverage = {
        "generated_at": built_at,
        "built_at": built_at,
        "upstream_generated_at": upstream_generated_at,
        "start_year": start_year,
        "channels": {
            **{
                snapshot.channel: {
                    **_channel_coverage(
                        snapshot,
                        included_records=sum(
                            record["_channel"] == snapshot.channel for record in all_records
                        ),
                        canonical_memberships=channel_counts.get(snapshot.channel, 0),
                    ),
                    "status": "stale" if snapshot.channel in stale else "ready",
                }
                for snapshot in snapshots
            },
            **{
                channel: {
                    "status": "pending",
                    "upstream_published_records": 0,
                    "included_records": 0,
                    "canonical_memberships": 0,
                }
                for channel in pending_channels
            },
        },
        "pending_channels": pending_channels,
        "stale_channels": stale,
        "failures": update_failures,
    }
    skipped = [
        {"channel": snapshot.channel, **item}
        for snapshot in snapshots
        for item in snapshot.diagnostics["skipped"]
    ]
    updates = {
        "generated_at": built_at,
        "built_at": built_at,
        "upstream_generated_at": upstream_generated_at,
        "data_version": data_version,
        "status": "partial" if pending_channels or stale or update_failures or skipped else "ok",
        "pending_channels": pending_channels,
        "stale_channels": stale,
        "failures": update_failures,
        "skipped": skipped,
        "counts": {
            "source_records": len(source_records),
            "included_records": len(all_records),
            "excluded_before_start_year": len(excluded_before_start_year),
            "papers": len(public_papers),
        },
    }
    report = {
        "schema_version": 2,
        "generated_at": built_at,
        "built_at": built_at,
        "upstream_generated_at": upstream_generated_at,
        "data_version": data_version,
        "start_year": start_year,
        "inputs": {
            snapshot.channel: {
                "source": snapshot.source,
                "diagnostics": snapshot.diagnostics,
            }
            for snapshot in snapshots
        },
        "pending_channels": pending_channels,
        "stale_channels": stale,
        "failures": update_failures,
        "channel_registry": [definition.public_dict() for definition in definitions],
        "counts": {
            "input_records": len(source_records),
            "included_records": len(all_records),
            "canonical_papers": len(public_papers),
            "deduplicated_records": len(all_records) - len(public_papers),
            "cross_channel_papers": sum(len(paper["channels"]) > 1 for paper in public_papers),
            "excluded_before_start_year": len(excluded_before_start_year),
            "skipped_records": len(skipped),
        },
        "excluded_before_start_year": excluded_before_start_year,
        "conflicts": conflicts,
        "skipped": skipped,
        "canonical_entities": [
            {
                "canonical_key": paper["_canonical_key"],
                "id": paper["id"],
                "channels": paper["channels"],
                "source_refs": paper["source_refs"],
                "unified_ingested_at": paper["unified_ingested_at"],
            }
            for paper in merged
        ],
    }

    replace_json_directory(output_dir / "papers", details)
    write_json(output_dir / "papers.json", public_papers)
    write_json(output_dir / "meta.json", meta)
    write_json(output_dir / "updates.json", updates)
    write_json(output_dir / "coverage.json", coverage)
    write_bytes(
        rss_path or output_dir.parent / "rss.xml",
        build_rss_xml(merged, built_at=built_at, site_url=site_url),
    )
    write_json(report_path, report)
    return report
