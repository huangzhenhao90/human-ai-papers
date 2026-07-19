"""Small-batch OpenAlex ingestion for the mental-health theme."""

from __future__ import annotations

import json
import math
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import httpx

from .config import iter_sources, load_theme_config, normalize_openalex_source_id, validate_source_identifiers
from .signals import evaluate_recall


OPENALEX_API = "https://api.openalex.org"
DEFAULT_CANDIDATES_PATH = Path("data/upstream/mh/candidates.json")
DEFAULT_REPORT_PATH = Path("data/upstream/mh/fetch_report.json")


class OpenAlexError(RuntimeError):
    """Raised after a bounded set of OpenAlex retries fails."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    positioned: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for position in positions or []:
            positioned.append((int(position), word))
    positioned.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned) or None


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class OpenAlexClient:
    def __init__(
        self,
        *,
        timeout: float = 20.0,
        retries: int = 3,
        contact_email: str = "anonymous@example.com",
        base_url: str = OPENALEX_API,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if retries < 1:
            raise ValueError("retries must be at least 1")
        self.retries = retries
        self.contact_email = contact_email
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": f"human-ai-papers/0.1 (mailto:{contact_email})"},
        )

    def close(self) -> None:
        self.client.close()

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "mailto": self.contact_email}
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.get(f"{self.base_url}/{path.lstrip('/')}", params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable OpenAlex status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise OpenAlexError(f"OpenAlex {path} returned a non-object response")
                return payload
            except (httpx.HTTPError, ValueError, OpenAlexError) as exc:
                last_error = exc
                if attempt < self.retries:
                    self.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
        raise OpenAlexError(f"OpenAlex {path} failed after {self.retries} attempts: {last_error}")

    def resolve_source(self, name: str, issn_l: str | None = None) -> dict[str, Any] | None:
        """Resolve only an exact display-name match, with ambiguity reported as unresolved."""
        payload = self._get_json("sources", {"search": name, "per-page": 10})
        exact = [
            item
            for item in payload.get("results") or []
            if str(item.get("display_name") or "").casefold() == name.casefold()
        ]
        if issn_l:
            issn_matches = [item for item in exact if str(item.get("issn_l") or "").casefold() == issn_l.casefold()]
            if len(issn_matches) == 1:
                exact = issn_matches
        if len(exact) != 1:
            return None
        item = exact[0]
        source_id = normalize_openalex_source_id(item.get("id"))
        if not source_id:
            return None
        return {
            "openalex_id": source_id,
            "display_name": item.get("display_name"),
            "issn_l": item.get("issn_l"),
            "type": item.get("type"),
            "resolution": "runtime_exact_name",
        }

    def fetch_works(
        self,
        *,
        source_id: str,
        from_date: str,
        to_date: str,
        limit: int,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = [
            f"primary_location.source.id:{source_id}",
            f"from_publication_date:{from_date}",
            f"to_publication_date:{to_date}",
        ]
        params: dict[str, Any] = {
            "filter": ",".join(filters),
            "per-page": min(200, max(1, limit)),
            "sort": "publication_date:desc",
            "cursor": "*",
        }
        if search:
            params["search"] = search

        collected: list[dict[str, Any]] = []
        while params.get("cursor") and len(collected) < limit:
            payload = self._get_json("works", params)
            collected.extend((payload.get("results") or [])[: limit - len(collected)])
            params["cursor"] = (payload.get("meta") or {}).get("next_cursor")
        return collected


def normalize_work(
    work: dict[str, Any],
    *,
    source: dict[str, Any],
    source_id: str,
    recall_decision: dict[str, Any],
    retrieved_at: str,
) -> dict[str, Any]:
    primary_location = work.get("primary_location") or {}
    best_oa_location = work.get("best_oa_location") or {}
    source_record = primary_location.get("source") or {}
    raw_doi = work.get("doi")
    doi = str(raw_doi).strip().lower().removeprefix("https://doi.org/") if raw_doi else None
    openalex_id = str(work.get("id") or "").rstrip("/").rsplit("/", 1)[-1] or None
    authors = [
        (authorship.get("author") or {}).get("display_name")
        for authorship in work.get("authorships") or []
        if (authorship.get("author") or {}).get("display_name")
    ]
    return {
        "id": openalex_id,
        "openalex_id": openalex_id,
        "doi": doi,
        "title": work.get("title") or work.get("display_name"),
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "publication_date": work.get("publication_date"),
        "publication_year": work.get("publication_year"),
        "type": work.get("type"),
        "language": work.get("language"),
        "authors": authors,
        "journal": source_record.get("display_name") or source.get("name"),
        "source_id": normalize_openalex_source_id(source_record.get("id")) or source_id,
        "source_key": source.get("key"),
        "source_layer": source.get("source_layer"),
        "source_type": source.get("source_type"),
        "ingest_mode": source.get("ingest_mode"),
        "cited_by": int(work.get("cited_by_count") or 0),
        "is_retracted": bool(work.get("is_retracted")),
        "url": primary_location.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else work.get("id")),
        "pdf_url": primary_location.get("pdf_url") or best_oa_location.get("pdf_url"),
        "recall": recall_decision,
        "retrieved_at": retrieved_at,
    }


def candidate_key(candidate: dict[str, Any]) -> str:
    if candidate.get("doi"):
        return f"doi:{candidate['doi']}"
    if candidate.get("openalex_id"):
        return f"openalex:{candidate['openalex_id']}"
    title = " ".join(str(candidate.get("title") or "").casefold().split())
    return f"title:{title}:{candidate.get('publication_year') or ''}"


def _validate_dates(from_date: str, to_date: str, minimum_date: str) -> None:
    try:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
        minimum = date.fromisoformat(minimum_date)
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD") from exc
    if start < minimum:
        raise ValueError(f"from_date must be on or after {minimum_date}")
    if start > end:
        raise ValueError("from_date must not be after to_date")


def run_fetch(
    *,
    config_path: str | Path | None = None,
    candidates_path: str | Path = DEFAULT_CANDIDATES_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
    dry_run: bool = False,
    timeout: float = 20.0,
    retries: int = 3,
    contact_email: str = "anonymous@example.com",
    client: OpenAlexClient | Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    config = load_theme_config(config_path)
    minimum_date = str(config["theme"].get("default_from_date") or "2023-01-01")
    from_date = from_date or minimum_date
    to_date = to_date or date.today().isoformat()
    _validate_dates(from_date, to_date, minimum_date)

    started_at = utc_now_iso()
    plans = list(iter_sources(config))
    validation = validate_source_identifiers(config)
    report: dict[str, Any] = {
        "schema_version": 1,
        "theme": "mh",
        "status": "dry_run" if dry_run else "running",
        "started_at": started_at,
        "finished_at": None,
        "parameters": {
            "from_date": from_date,
            "to_date": to_date,
            "limit": limit,
            "dry_run": dry_run,
            "timeout_seconds": timeout,
            "retries": retries,
        },
        "source_validation": validation,
        "sources": [],
        "counts": {"planned_sources": len(plans), "raw_works": 0, "deduplicated": 0, "candidates": 0},
        "failures": [],
    }
    if dry_run or limit == 0:
        report["status"] = "dry_run" if dry_run else "success"
        report["finished_at"] = utc_now_iso()
        _atomic_write_json(Path(candidates_path), [])
        _atomic_write_json(Path(report_path), report)
        return [], report

    owns_client = client is None
    active_client = client or OpenAlexClient(
        timeout=timeout,
        retries=retries,
        contact_email=contact_email,
    )
    query_pairs = ((config.get("recall") or {}).get("openalex_query_pairs") or [])
    per_source_limit = max(1, min(5, math.ceil(limit / max(1, len(plans)))))
    gathered: dict[str, dict[str, Any]] = {}
    retrieved_at = utc_now_iso()

    try:
        for source_index, source in enumerate(plans):
            source_report: dict[str, Any] = {
                "key": source.get("key"),
                "name": source.get("name"),
                "source_layer": source.get("source_layer"),
                "ingest_mode": source.get("ingest_mode"),
                "configured_openalex_id": normalize_openalex_source_id(source.get("openalex_id")),
                "resolved_openalex_id": None,
                "resolution": None,
                "query": None,
                "raw_works": 0,
                "accepted": 0,
                "status": "pending",
            }
            report["sources"].append(source_report)
            try:
                source_id = normalize_openalex_source_id(source.get("openalex_id"))
                if source_id:
                    source_report["resolution"] = "verified_config"
                else:
                    resolved = active_client.resolve_source(source["name"], source.get("issn_l"))
                    source_id = (resolved or {}).get("openalex_id")
                    source_report["resolution"] = (resolved or {}).get("resolution") or "unresolved"
                source_report["resolved_openalex_id"] = source_id
                if not source_id:
                    source_report["status"] = "skipped_unresolved_source"
                    continue

                search_query = None
                if source.get("ingest_mode") == "query" and query_pairs:
                    search_query = str(query_pairs[source_index % len(query_pairs)])
                source_report["query"] = search_query
                works = active_client.fetch_works(
                    source_id=source_id,
                    from_date=from_date,
                    to_date=to_date,
                    limit=per_source_limit,
                    search=search_query,
                )
                source_report["raw_works"] = len(works)
                report["counts"]["raw_works"] += len(works)
                for work in works:
                    title = work.get("title") or work.get("display_name")
                    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                    decision = evaluate_recall(title, abstract, config)
                    if source.get("ingest_mode") == "query" and not decision["eligible"]:
                        continue
                    candidate = normalize_work(
                        work,
                        source=source,
                        source_id=source_id,
                        recall_decision=decision,
                        retrieved_at=retrieved_at,
                    )
                    key = candidate_key(candidate)
                    if key not in gathered:
                        gathered[key] = candidate
                        source_report["accepted"] += 1
                source_report["status"] = "success"
            except Exception as exc:  # one source must not abort the remaining sources
                source_report["status"] = "failed"
                source_report["error"] = str(exc)
                report["failures"].append({"source": source.get("key"), "error": str(exc)})
    finally:
        if owns_client:
            active_client.close()

    candidates = sorted(
        gathered.values(),
        # Full-source works remain eligible for post-scoring, but a bounded validation
        # batch should surface dual-signal records before newer unrelated full-journal work.
        key=lambda item: (
            bool((item.get("recall") or {}).get("eligible")),
            item.get("publication_date") or "",
            item.get("cited_by") or 0,
        ),
        reverse=True,
    )[:limit]
    report["counts"]["deduplicated"] = len(gathered)
    report["counts"]["candidates"] = len(candidates)
    report["status"] = "partial_failure" if report["failures"] else "success"
    report["finished_at"] = utc_now_iso()
    _atomic_write_json(Path(candidates_path), candidates)
    _atomic_write_json(Path(report_path), report)
    return candidates, report
