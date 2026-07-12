"""Normalize channel exports and merge them into canonical paper entities."""

from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

from .stable_id import (
    canonical_key,
    normalize_arxiv_id,
    normalize_doi,
    normalize_text,
    stable_public_id,
)


COMMON_FIELDS = (
    "title",
    "title_zh",
    "date",
    "year",
    "journal",
    "authors",
    "authors_full",
    "volume",
    "issue",
    "abstract",
    "cited_by",
    "url",
    "pdf_url",
    "ai_type_tags",
)
PROFILE_FIELDS = (
    "ai_score",
    "domain_score",
    "ai_reason",
    "tldr",
    "topic_tags",
    "evidence_stage",
    "clinical_validation",
    "safety_evaluated",
    "real_world_deployment",
    "ground_truth_quality",
    "risk_tags",
)


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        flattened: list[Any] = []
        for nested in value.values():
            flattened.extend(nested if isinstance(nested, list) else [nested])
        value = flattened
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            item = item.get("name") or item.get("label")
        if _present(item):
            result.append(str(item))
    return result


def normalize_channel_record(
    record: Mapping[str, Any],
    *,
    channel: str,
    revision: str | None = None,
    source_generated_at: str | None = None,
) -> dict[str, Any]:
    """Normalize one legacy/native record without discarding channel judgments."""

    normalized = deepcopy(dict(record))
    normalized["_channel"] = channel
    normalized["_canonical_key"] = canonical_key({**record, "_channel": channel})
    normalized["authors"] = _as_string_list(record.get("authors"))
    normalized["topic_tags"] = _as_string_list(record.get("topic_tags"))
    normalized["ai_type_tags"] = _as_string_list(record.get("ai_type_tags"))
    normalized["ai_score"] = record.get("ai_score", record.get("ai_relevance"))
    normalized["domain_score"] = record.get(
        "domain_score", record.get("domain_relevance")
    )
    normalized["tldr"] = record.get("tldr", record.get("tldr_zh"))
    normalized["doi"] = normalize_doi(record.get("doi")) or normalize_doi(record.get("url"))
    normalized["arxiv_id"] = next(
        (
            found
            for field in ("arxiv_id", "url", "pdf_url")
            if (found := normalize_arxiv_id(record.get(field)))
        ),
        None,
    )
    normalized["_source_revision"] = revision
    normalized["_source_generated_at"] = source_generated_at
    normalized["_source_updated_at"] = str(
        record.get("scored_at")
        or record.get("updated_at")
        or record.get("ingested_at")
        or source_generated_at
        or ""
    )
    return normalized


def _record_rank(record: Mapping[str, Any]) -> tuple[int, str, str]:
    completeness = sum(_present(record.get(field)) for field in COMMON_FIELDS)
    stable_tie_breaker = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    return completeness, str(record.get("_source_updated_at") or ""), stable_tie_breaker


def _profile(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: deepcopy(record.get(field))
        for field in PROFILE_FIELDS
        if _present(record.get(field)) or field in {"ai_score", "domain_score", "topic_tags", "tldr"}
    }


def _merge_group(key: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(records, key=_record_rank, reverse=True)
    merged: dict[str, Any] = {"id": stable_public_id(key)}
    for field in COMMON_FIELDS:
        value = next((record.get(field) for record in ranked if _present(record.get(field))), None)
        if field in {"authors", "ai_type_tags"}:
            value = _as_string_list(value)
        merged[field] = deepcopy(value)

    doi = next((record.get("doi") for record in ranked if record.get("doi")), None)
    arxiv_id = next((record.get("arxiv_id") for record in ranked if record.get("arxiv_id")), None)
    merged["doi"] = doi
    merged["arxiv_id"] = arxiv_id
    merged["cited_by"] = max(
        (int(record.get("cited_by") or 0) for record in records), default=0
    )

    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_channel[str(record["_channel"])].append(record)
    merged["channels"] = sorted(by_channel)
    merged["channel_profiles"] = {
        channel: _profile(sorted(channel_records, key=_record_rank, reverse=True)[0])
        for channel, channel_records in sorted(by_channel.items())
    }
    merged["source_refs"] = sorted(
        (
            {
                "channel": str(record["_channel"]),
                "legacy_id": record.get("id"),
                **(
                    {"revision": record["_source_revision"]}
                    if record.get("_source_revision")
                    else {}
                ),
            }
            for record in records
        ),
        key=lambda ref: (ref["channel"], str(ref.get("legacy_id"))),
    )
    merged["_canonical_key"] = key
    return merged


def _year(record: Mapping[str, Any]) -> int | None:
    value = record.get("year") or str(record.get("date") or "")[:4]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compatible_identity(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_year, right_year = _year(left), _year(right)
    if left_year is not None and right_year is not None and abs(left_year - right_year) > 1:
        return False
    left_title = normalize_text(left.get("title"))
    right_title = normalize_text(right.get("title"))
    if left_title and right_title:
        return SequenceMatcher(None, left_title, right_title).ratio() >= 0.5
    return True


def _identity_signature(record: Mapping[str, Any]) -> str:
    authors = record.get("authors") or []
    first_author = authors[0] if isinstance(authors, list) and authors else ""
    return "\x1f".join(
        (normalize_text(record.get("title")), str(_year(record) or ""), normalize_text(first_author))
    )


def _partition_conflicts(
    key: str, records: list[dict[str, Any]]
) -> tuple[list[tuple[str, list[dict[str, Any]]]], dict[str, Any] | None]:
    if key.startswith("fingerprint:") or len(records) < 2:
        return [(key, records)], None
    clusters: list[list[dict[str, Any]]] = []
    for record in sorted(records, key=_identity_signature):
        matching = next(
            (cluster for cluster in clusters if _compatible_identity(cluster[0], record)), None
        )
        if matching is None:
            clusters.append([record])
        else:
            matching.append(record)
    if len(clusters) == 1:
        return [(key, clusters[0])], None

    resolved: list[tuple[str, list[dict[str, Any]]]] = []
    variants: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters):
        signature = _identity_signature(cluster[0])
        cluster_key = key if index == 0 else (
            f"{key}|conflict:{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:16]}"
        )
        resolved.append((cluster_key, cluster))
        variants.append(
            {
                "resolved_key": cluster_key,
                "title": cluster[0].get("title"),
                "year": _year(cluster[0]),
                "source_refs": [
                    {"channel": item["_channel"], "legacy_id": item.get("id")}
                    for item in cluster
                ],
            }
        )
    return resolved, {
        "canonical_key": key,
        "reason": "critical title or publication-year mismatch",
        "variants": variants,
    }


def merge_channel_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Merge normalized records, deterministically, by canonical identity."""

    merged, _ = merge_channel_records_with_diagnostics(records)
    return merged


def merge_channel_records_with_diagnostics(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge records and return any canonical-key collision decisions."""

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        materialized = dict(record)
        if "_canonical_key" not in materialized:
            channel = str(materialized.get("channel") or materialized.get("_channel") or "unknown")
            materialized = normalize_channel_record(materialized, channel=channel)
        groups[str(materialized["_canonical_key"])].append(materialized)

    resolved_groups: list[tuple[str, list[dict[str, Any]]]] = []
    conflicts: list[dict[str, Any]] = []
    for key in sorted(groups):
        partitions, conflict = _partition_conflicts(key, groups[key])
        resolved_groups.extend(partitions)
        if conflict is not None:
            conflicts.append(conflict)
    merged = [_merge_group(key, group) for key, group in resolved_groups]
    return sorted(
        merged,
        key=lambda paper: (str(paper.get("date") or ""), str(paper.get("title") or ""), paper["id"]),
        reverse=True,
    ), conflicts
