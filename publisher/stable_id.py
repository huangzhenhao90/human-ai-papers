"""Canonical paper keys and deterministic public IDs."""

from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from typing import Any, Mapping
from urllib.parse import unquote


_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_DOI_VALUE = re.compile(r"10\.\d{4,9}/[^\s?#]+", re.IGNORECASE)
_ARXIV_VALUE = re.compile(
    r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)|"
    r"(?<![\w.-])([a-z-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?(?!\d)",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalize_doi(value: Any) -> str | None:
    """Return a lowercase bare DOI, or ``None`` when no DOI is present."""

    if value is None:
        return None
    candidate = unquote(str(value)).strip()
    candidate = _DOI_PREFIX.sub("", candidate)
    match = _DOI_VALUE.search(candidate)
    if not match:
        return None
    return match.group(0).rstrip(".,;").casefold()


def normalize_arxiv_id(value: Any) -> str | None:
    """Extract an arXiv identifier and remove its version suffix."""

    if value is None:
        return None
    match = _ARXIV_VALUE.search(unquote(str(value)))
    if not match:
        return None
    return (match.group(1) or match.group(2)).casefold()


def normalize_text(value: Any) -> str:
    """Normalize human text for identity comparisons, not for display."""

    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(_NON_WORD.sub(" ", text).split())


def _publication_year(record: Mapping[str, Any]) -> str:
    year = record.get("year")
    if year not in (None, ""):
        match = re.search(r"\d{4}", str(year))
        if match:
            return match.group(0)
    match = re.search(r"\d{4}", str(record.get("date") or ""))
    return match.group(0) if match else ""


def _first_author(record: Mapping[str, Any]) -> str:
    authors = record.get("authors")
    if isinstance(authors, list) and authors:
        first = authors[0]
        if isinstance(first, Mapping):
            return str(first.get("name") or "")
        return str(first)
    authors_full = record.get("authors_full")
    if isinstance(authors_full, list) and authors_full:
        first = authors_full[0]
        if isinstance(first, Mapping):
            return str(first.get("name") or "")
        return str(first)
    return ""


def canonical_key(record: Mapping[str, Any]) -> str:
    """Build the DOI -> arXiv -> title/year/author identity key."""

    doi = normalize_doi(record.get("doi")) or normalize_doi(record.get("url"))
    if doi:
        return f"doi:{doi}"

    for field in ("arxiv_id", "url", "pdf_url", "doi"):
        arxiv_id = normalize_arxiv_id(record.get(field))
        if arxiv_id:
            return f"arxiv:{arxiv_id}"

    title = normalize_text(record.get("title"))
    if not title:
        channel = record.get("channel") or record.get("_channel") or "unknown"
        legacy_id = record.get("id", "unknown")
        raise ValueError(
            "cannot build canonical key: missing title "
            f"(channel={channel}, legacy_id={legacy_id})"
        )
    fingerprint = "\x1f".join(
        (title, _publication_year(record), normalize_text(_first_author(record)))
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"fingerprint:{digest}"


def stable_public_id(key: str) -> str:
    """Return a short URL-safe ID derived only from a canonical key."""

    digest = hashlib.sha256(key.encode("utf-8")).digest()[:12]
    token = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"p_{token}"
