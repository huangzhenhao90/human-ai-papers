"""Generate the unified RSS feed from first-seen timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree


CHANNEL_NAMES = {
    "ob": "组织与商业",
    "ur": "用户与交互",
    "mh": "心理健康",
}
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"


def _timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_rss_xml(
    papers: list[dict[str, Any]],
    *,
    built_at: str,
    site_url: str = "http://localhost:3000",
    limit: int = 30,
) -> bytes:
    site_url = site_url.rstrip("/")
    ElementTree.register_namespace("atom", ATOM_NAMESPACE)
    rss = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel")
    ElementTree.SubElement(channel, "title").text = "AI Papers"
    ElementTree.SubElement(channel, "link").text = site_url
    ElementTree.SubElement(
        channel,
        f"{{{ATOM_NAMESPACE}}}link",
        {"href": f"{site_url}/rss.xml", "rel": "self", "type": "application/rss+xml"},
    )
    ElementTree.SubElement(channel, "description").text = (
        "AI 如何改变人、组织与心理健康；按首次进入统一索引时间更新"
    )
    ElementTree.SubElement(channel, "language").text = "zh-CN"
    ElementTree.SubElement(channel, "lastBuildDate").text = format_datetime(
        _timestamp(built_at), usegmt=True
    )
    ElementTree.SubElement(channel, "generator").text = "human-ai-papers publisher"

    ordered = sorted(
        papers,
        key=lambda paper: (
            str(paper.get("unified_ingested_at") or ""),
            str(paper.get("date") or ""),
            paper["id"],
        ),
        reverse=True,
    )
    for paper in ordered[:limit]:
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "title").text = str(
            paper.get("title_zh") or paper.get("title") or "Untitled"
        )
        paper_link = f"{site_url}/papers/{quote(paper['id'], safe='')}"
        ElementTree.SubElement(item, "link").text = paper_link
        ElementTree.SubElement(item, "guid", {"isPermaLink": "true"}).text = paper_link
        ElementTree.SubElement(item, "pubDate").text = format_datetime(
            _timestamp(paper.get("unified_ingested_at")), usegmt=True
        )
        profiles = paper.get("channel_profiles") or {}
        description = next(
            (
                profile.get("tldr")
                for channel_id in ("mh", "ur", "ob")
                if (profile := profiles.get(channel_id)) and profile.get("tldr")
            ),
            paper.get("title"),
        )
        if description:
            ElementTree.SubElement(item, "description").text = str(description)
        for channel_id in paper.get("channels") or []:
            ElementTree.SubElement(item, "category").text = CHANNEL_NAMES.get(
                channel_id, channel_id
            )
    ElementTree.indent(rss, space="  ")
    return ElementTree.tostring(rss, encoding="utf-8", xml_declaration=True) + b"\n"
