"""Adapters for legacy OB/UR exports and the native MH export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import read_json
from .merge_channels import normalize_channel_record


@dataclass(frozen=True)
class ChannelSnapshot:
    channel: str
    records: list[dict[str, Any]]
    meta: dict[str, Any]
    source: dict[str, Any]
    diagnostics: dict[str, Any]


def _record_id(record: dict[str, Any], fallback: int) -> str:
    return str(record.get("id")) if record.get("id") is not None else f"__row_{fallback}"


def load_channel_snapshot(path: Path, channel: str) -> ChannelSnapshot:
    context = f"load channel={channel} snapshot={path}"
    compact = read_json(path / "papers.json", context=context)
    full = read_json(path / "papers_full.json", context=context)
    meta = read_json(path / "meta.json", context=context)
    source_path = path / "_source.json"
    source = read_json(source_path, context=context) if source_path.exists() else {}
    if not isinstance(compact, list):
        raise RuntimeError(f"{context}: papers.json must be an array")
    if not isinstance(full, list):
        raise RuntimeError(f"{context}: papers_full.json must be an array")
    if not isinstance(meta, dict):
        raise RuntimeError(f"{context}: meta.json must be an object")

    full_by_id: dict[str, dict[str, Any]] = {}
    duplicate_full_ids: list[str] = []
    for index, item in enumerate(full):
        if not isinstance(item, dict):
            raise RuntimeError(f"{context}: papers_full.json row {index} must be an object")
        identity = _record_id(item, index)
        if identity in full_by_id:
            duplicate_full_ids.append(identity)
        full_by_id[identity] = item

    normalized: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    compact_ids: set[str] = set()
    for index, item in enumerate(compact):
        if not isinstance(item, dict):
            skipped.append({"row": index, "reason": "papers.json row is not an object"})
            continue
        identity = _record_id(item, index)
        compact_ids.add(identity)
        combined = {**full_by_id.get(identity, {}), **item}
        try:
            normalized.append(
                normalize_channel_record(
                    combined,
                    channel=channel,
                    revision=source.get("revision"),
                    source_generated_at=meta.get("generated_at") or source.get("generated_at"),
                )
            )
        except (TypeError, ValueError) as exc:
            skipped.append({"row": index, "legacy_id": item.get("id"), "reason": str(exc)})

    diagnostics = {
        "input_compact": len(compact),
        "input_full": len(full),
        "normalized": len(normalized),
        "missing_full_ids": sorted(compact_ids - set(full_by_id)),
        "full_only_ids": sorted(set(full_by_id) - compact_ids),
        "duplicate_full_ids": sorted(set(duplicate_full_ids)),
        "skipped": skipped,
    }
    return ChannelSnapshot(channel, normalized, meta, source, diagnostics)
