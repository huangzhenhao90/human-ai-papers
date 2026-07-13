"""Validate the cross-file public release contract before publishing."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .io_utils import read_json


PUBLIC_ID = re.compile(r"p_[A-Za-z0-9_-]{16}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"release validation failed: {message}")


def validate_release(
    *,
    output_dir: Path,
    report_path: Path,
    rss_path: Path,
    require_all_channels: bool = True,
) -> dict[str, Any]:
    papers = read_json(output_dir / "papers.json", context="validate public papers")
    meta = read_json(output_dir / "meta.json", context="validate public meta")
    coverage = read_json(output_dir / "coverage.json", context="validate coverage")
    updates = read_json(output_dir / "updates.json", context="validate updates")
    report = read_json(report_path, context="validate publish report")
    _require(isinstance(papers, list), "papers.json must be an array")
    for name, value in (("meta", meta), ("coverage", coverage), ("updates", updates), ("report", report)):
        _require(isinstance(value, dict), f"{name} must be an object")

    ids = [str(paper.get("id") or "") for paper in papers]
    _require(len(ids) == len(set(ids)), "public ids must be unique")
    _require(all(PUBLIC_ID.fullmatch(identifier) for identifier in ids), "public ids must be stable URL-safe ids")
    _require(len(papers) == int(meta.get("totals", {}).get("papers", -1)), "meta paper count mismatch")
    _require(len(papers) == int(report.get("counts", {}).get("canonical_papers", -1)), "report paper count mismatch")
    _require(meta.get("data_version") == updates.get("data_version") == report.get("data_version"), "data_version mismatch")

    start_year = int(meta.get("start_year") or 0)
    _require(
        all(not paper.get("year") or int(paper["year"]) >= start_year for paper in papers),
        "a paper predates the configured start year",
    )
    channel_meta = meta.get("channels", {})
    _require(isinstance(channel_meta, dict) and channel_meta, "meta must contain a channel registry")
    channel_ids = set(channel_meta)
    memberships = Counter(channel for paper in papers for channel in paper.get("channels") or [])
    _require(set(memberships).issubset(channel_ids), "papers contain an unregistered channel")
    orders: list[int] = []
    for channel, definition in channel_meta.items():
        _require(isinstance(definition, dict), f"channel={channel} metadata must be an object")
        for field in ("short", "label", "description", "color", "soft_color", "order", "required", "status"):
            _require(field in definition, f"channel={channel} is missing registry field={field}")
        orders.append(int(definition["order"]))
        expected = int(definition.get("papers", -1))
        _require(memberships[channel] == expected, f"channel={channel} count mismatch")
    _require(len(orders) == len(set(orders)), "channel order values must be unique")

    detail_dir = output_dir / "papers"
    details = {path.stem for path in detail_dir.glob("*.json")}
    _require(details == set(ids), "detail files must match the public paper ids exactly")
    pending = set(updates.get("pending_channels") or [])
    if require_all_channels:
        _require(not pending, f"pending channels are not allowed: {sorted(pending)}")

    coverage_channels = coverage.get("channels", {})
    _require(all(channel in coverage_channels for channel in channel_ids), "coverage must include all registered channels")
    stale = set(updates.get("stale_channels") or [])
    _require(stale.issubset(channel_ids), "updates contains an unregistered stale channel")
    try:
        rss = ElementTree.parse(rss_path)
    except (ElementTree.ParseError, OSError) as exc:
        raise RuntimeError(f"release validation failed: invalid RSS: {exc}") from exc
    rss_items = rss.findall("./channel/item")
    _require(len(rss_items) <= 30, "RSS must contain at most 30 items")
    _require(all("/papers/p_" in (item.findtext("guid") or "") for item in rss_items), "RSS contains an invalid paper guid")

    return {
        "status": "passed",
        "papers": len(papers),
        "details": len(details),
        "rss_items": len(rss_items),
        "channels": dict(sorted(memberships.items())),
        "data_version": meta.get("data_version"),
        "update_status": updates.get("status"),
        "stale_channels": sorted(stale),
        "failures": updates.get("failures") or [],
    }
