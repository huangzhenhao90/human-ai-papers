"""Bounded MiniMax scoring and publisher-compatible MH snapshots."""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import httpx

from .config import load_theme_config
from .signals import evaluate_recall, false_positive_domain_cap


DEFAULT_INPUT_PATH = Path("data/upstream/mh/candidates.json")
DEFAULT_OUTPUT_DIR = Path("data/exports/mental-health")
DEFAULT_SCORE_REPORT = "score_report.json"


class MissingAPIKeyError(RuntimeError):
    """Raised when an explicitly requested paid run has no MiniMax key."""


class ScoringContractError(ValueError):
    """Raised when the LLM response cannot satisfy the scoring contract."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_candidates(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Mental-health candidates do not exist: {input_path}")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("candidates")
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ScoringContractError("Candidates input must be a JSON array of objects")
    return payload


def extract_json_array(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(r"```(?:json)?\s*", "", text or "", flags=re.IGNORECASE).strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start < 0 or end < start:
        raise ScoringContractError("MiniMax response did not contain a JSON array")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ScoringContractError(f"MiniMax response contained invalid JSON: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ScoringContractError("MiniMax response JSON must be an array of objects")
    return payload


def controlled_tag_ids(config: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for group, items in (config.get("controlled_tags") or {}).items():
        result[group] = {str(item["id"]) for item in items or [] if isinstance(item, dict) and item.get("id")}
    return result


def build_system_prompt(config: dict[str, Any]) -> str:
    controlled = {group: sorted(values) for group, values in controlled_tag_ids(config).items()}
    false_positive_summary = [
        {
            "id": rule.get("id"),
            "description": rule.get("description"),
            "max_domain_score": rule.get("max_domain_score", 2),
        }
        for rule in config.get("false_positive_rules") or []
    ]
    clinical = (config.get("assessment_fields") or {}).get("clinical_validation") or []
    ground_truth = (config.get("assessment_fields") or {}).get("ground_truth_quality") or []
    return f"""You are a strict academic reviewer for the Mental Health x AI paper channel.

Score each paper independently on two 0-5 dimensions:
- ai_relevance: 5 AI is the core object/method; 4 major component; 3 substantive but secondary; 2 background mention; 1 ambiguous automation; 0 absent.
- domain_relevance: 5 core mental-health outcome/service/assessment; 4 strongly relevant; 3 substantive mental-health component; 2 wording-only or adjacent; 1 extremely weak; 0 absent.

Publication requires BOTH ai_relevance >= 3 AND domain_relevance >= 3. Keywords only recall candidates and never prove relevance.
The following false recalls MUST have domain_relevance <= 2 unless the paper contains the stated genuine mental-health exception:
{json.dumps(false_positive_summary, ensure_ascii=False)}
Also cap generic medical AI, pure algorithms/datasets, pure neuroimaging/biomarker modelling without a mental-health service, assessment, intervention, or outcome at domain_relevance <= 2.

For evidence, distinguish conceptual, benchmark development, retrospective validation, user study, prospective study, real-world deployment, randomized trial, and systematic review. Do not infer clinical validation, safety evaluation, deployment, sample, or outcomes when the abstract does not state them; use null/unknown/false.

Only use these controlled tag IDs; never invent tags:
{json.dumps(controlled, ensure_ascii=False)}
clinical_validation must be one of: {json.dumps(clinical, ensure_ascii=False)}
ground_truth_quality must be one of: {json.dumps(ground_truth, ensure_ascii=False)}

Return ONLY a JSON array. Each object must have:
{{"id":"same input id","ai_relevance":0,"domain_relevance":0,"rationale_zh":"<=60 Chinese chars","title_zh":"faithful Chinese title or null","tldr_zh":"one evidence-calibrated Chinese sentence or null","evidence_stage":"controlled evidence_stages id","clinical_validation":"allowed value","safety_evaluated":false,"real_world_deployment":false,"ground_truth_quality":"allowed value","evidence":{{"study_design":"stated design or null","sample":"stated sample or null","outcomes":"stated outcomes or null"}},"controlled_tags":{{"conditions":[],"applications":[],"populations":[],"ai_types":[],"risks":[]}}}}
"""


def format_batch(candidates: list[dict[str, Any]]) -> str:
    papers = []
    for candidate in candidates:
        papers.append(
            {
                "id": candidate.get("id") or candidate.get("openalex_id"),
                "title": candidate.get("title"),
                "abstract": (candidate.get("abstract") or "")[:4000],
                "source": candidate.get("journal"),
                "date": candidate.get("publication_date") or candidate.get("date"),
            }
        )
    return "Score these papers:\n" + json.dumps(papers, ensure_ascii=False)


class MiniMaxScoringClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        chat_path: str = "/text/chatcompletion_v2",
        timeout: float = 180.0,
        retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise MissingAPIKeyError("MINIMAX_API_KEY is required for --execute")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.chat_path = "/" + chat_path.lstrip("/")
        self.retries = max(1, retries)
        self.sleep = sleep
        self.client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "MiniMaxScoringClient":
        env = os.environ if environ is None else environ
        api_key = env.get("MINIMAX_API_KEY", "").strip()
        if not api_key:
            raise MissingAPIKeyError(
                "MINIMAX_API_KEY is missing. Default dry-run is safe; set the key and pass --execute for a paid batch."
            )
        return cls(
            api_key=api_key,
            base_url=env.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
            model=env.get("MINIMAX_MODEL", "MiniMax-M2.7"),
            chat_path=env.get("MINIMAX_CHAT_PATH", "/text/chatcompletion_v2"),
            timeout=float(env.get("MINIMAX_TIMEOUT", "180")),
            retries=int(env.get("MINIMAX_RETRIES", "3")),
        )

    def close(self) -> None:
        self.client.close()

    def score_batch(self, candidates: list[dict[str, Any]], system_prompt: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": format_batch(candidates)},
            ],
            "temperature": 0.0,
            "max_tokens": 1800 + 350 * len(candidates),
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.post(f"{self.base_url}{self.chat_path}", json=payload)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable MiniMax status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
                base_response = data.get("base_resp") or {}
                if base_response.get("status_code") not in (None, 0):
                    raise ScoringContractError(f"MiniMax API error: {base_response}")
                message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                return extract_json_array(message), data.get("usage") or {}
            except (httpx.HTTPError, ValueError, ScoringContractError) as exc:
                last_error = exc
                if attempt < self.retries:
                    self.sleep(min(15.0, float(2 ** (attempt - 1))))
        raise RuntimeError(f"MiniMax scoring failed after {self.retries} attempts: {last_error}")


def _bounded_score(value: Any, field: str) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ScoringContractError(f"{field} must be numeric") from exc
    if not 0 <= number <= 5:
        raise ScoringContractError(f"{field} must be in 0..5")
    return number


def _bool(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.casefold() == "true")


def sanitize_score(raw: dict[str, Any], candidate: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    expected_id = str(candidate.get("id") or candidate.get("openalex_id") or "")
    returned_id = str(raw.get("id") or "")
    if not expected_id or returned_id != expected_id:
        raise ScoringContractError(f"Score id {returned_id!r} did not match candidate {expected_id!r}")

    ai_score = _bounded_score(raw.get("ai_relevance"), "ai_relevance")
    domain_score = _bounded_score(raw.get("domain_relevance"), "domain_relevance")
    recall_decision = evaluate_recall(candidate.get("title"), candidate.get("abstract"), config)
    cap = false_positive_domain_cap(recall_decision)
    domain_capped = cap is not None and domain_score > cap
    if cap is not None:
        domain_score = min(domain_score, cap)

    allowed = controlled_tag_ids(config)
    raw_tags = raw.get("controlled_tags") if isinstance(raw.get("controlled_tags"), dict) else {}
    tags: dict[str, list[str]] = {}
    for group in ("conditions", "applications", "populations", "ai_types", "risks"):
        values = raw_tags.get(group) if isinstance(raw_tags, dict) else []
        tags[group] = list(dict.fromkeys(str(value) for value in values or [] if str(value) in allowed.get(group, set())))

    evidence_stage = str(raw.get("evidence_stage") or "conceptual")
    if evidence_stage not in allowed.get("evidence_stages", set()):
        evidence_stage = "conceptual"
    assessment = config.get("assessment_fields") or {}
    clinical_allowed = set(assessment.get("clinical_validation") or [])
    ground_truth_allowed = set(assessment.get("ground_truth_quality") or [])
    clinical_validation = str(raw.get("clinical_validation") or "none")
    if clinical_validation not in clinical_allowed:
        clinical_validation = "none"
    ground_truth = str(raw.get("ground_truth_quality") or "unknown")
    if ground_truth not in ground_truth_allowed:
        ground_truth = "unknown"
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}

    return {
        "id": expected_id,
        "ai_relevance": ai_score,
        "domain_relevance": domain_score,
        "rationale_zh": str(raw.get("rationale_zh") or "")[:240],
        "title_zh": str(raw.get("title_zh"))[:500] if raw.get("title_zh") else None,
        "tldr_zh": str(raw.get("tldr_zh"))[:800] if raw.get("tldr_zh") else None,
        "evidence_stage": evidence_stage,
        "clinical_validation": clinical_validation,
        "safety_evaluated": _bool(raw.get("safety_evaluated")),
        "real_world_deployment": _bool(raw.get("real_world_deployment")),
        "ground_truth_quality": ground_truth,
        "evidence": {
            "study_design": evidence.get("study_design"),
            "sample": evidence.get("sample"),
            "outcomes": evidence.get("outcomes"),
        },
        "controlled_tags": tags,
        "local_recall_audit": recall_decision,
        "domain_score_capped_by_false_positive_rule": domain_capped,
    }


def public_record(candidate: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    tags = score["controlled_tags"]
    topic_tags = list(dict.fromkeys(tags["conditions"] + tags["applications"] + tags["populations"]))
    profile = {
        "ai_score": score["ai_relevance"],
        "domain_score": score["domain_relevance"],
        "ai_reason": score["rationale_zh"],
        "tldr": score["tldr_zh"],
        "topic_tags": topic_tags,
        "ai_type_tags": tags["ai_types"],
        "evidence_stage": score["evidence_stage"],
        "risk_tags": tags["risks"],
    }
    return {
        "id": candidate.get("id") or candidate.get("openalex_id"),
        "doi": candidate.get("doi"),
        "title": candidate.get("title"),
        "title_zh": score["title_zh"],
        "journal": candidate.get("journal"),
        "year": candidate.get("publication_year") or str(candidate.get("publication_date") or "")[:4] or None,
        "date": candidate.get("publication_date"),
        "authors": (candidate.get("authors") or [])[:10],
        "url": candidate.get("url"),
        "pdf_url": candidate.get("pdf_url"),
        "cited_by": int(candidate.get("cited_by") or 0),
        "ai_score": score["ai_relevance"],
        "domain_score": score["domain_relevance"],
        "ai_reason": score["rationale_zh"],
        "tldr": score["tldr_zh"],
        "topic_tags": topic_tags,
        "ai_type_tags": tags["ai_types"],
        "evidence_stage": score["evidence_stage"],
        "clinical_validation": score["clinical_validation"],
        "safety_evaluated": score["safety_evaluated"],
        "real_world_deployment": score["real_world_deployment"],
        "ground_truth_quality": score["ground_truth_quality"],
        "risk_tags": tags["risks"],
        "channel": "mh",
        "channel_profile": profile,
    }


def full_record(candidate: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    record = public_record(candidate, score)
    record.update(
        {
            "abstract": candidate.get("abstract"),
            "authors_full": [{"name": name} for name in candidate.get("authors") or []],
            "openalex_id": candidate.get("openalex_id"),
            "source": {
                "key": candidate.get("source_key"),
                "id": candidate.get("source_id"),
                "layer": candidate.get("source_layer"),
                "type": candidate.get("source_type"),
                "ingest_mode": candidate.get("ingest_mode"),
            },
            "mh_profile": {
                **record["channel_profile"],
                "clinical_validation": score["clinical_validation"],
                "safety_evaluated": score["safety_evaluated"],
                "real_world_deployment": score["real_world_deployment"],
                "ground_truth_quality": score["ground_truth_quality"],
                "evidence": score["evidence"],
                "controlled_tags": score["controlled_tags"],
                "local_recall_audit": score["local_recall_audit"],
                "domain_score_capped_by_false_positive_rule": score[
                    "domain_score_capped_by_false_positive_rule"
                ],
            },
        }
    )
    return record


def _write_exports(
    *,
    output_dir: Path,
    candidates: list[dict[str, Any]],
    scored: list[tuple[dict[str, Any], dict[str, Any]]],
    config: dict[str, Any],
    status: str,
    dry_run: bool,
    model: str | None,
    failures: list[dict[str, Any]],
    usage: dict[str, int],
) -> dict[str, Any]:
    thresholds = config["theme"]["publish_thresholds"]
    publishable = [
        (candidate, score)
        for candidate, score in scored
        if score["ai_relevance"] >= int(thresholds["ai_relevance"])
        and score["domain_relevance"] >= int(thresholds["domain_relevance"])
    ]
    public = [public_record(candidate, score) for candidate, score in publishable]
    full = [full_record(candidate, score) for candidate, score in publishable]
    public.sort(key=lambda item: (item.get("date") or "", item.get("cited_by") or 0), reverse=True)
    full.sort(key=lambda item: (item.get("date") or "", item.get("cited_by") or 0), reverse=True)

    journal_counts = Counter(item.get("journal") or "Unknown" for item in public)
    topic_counts = Counter(tag for item in public for tag in item.get("topic_tags") or [])
    ai_type_counts = Counter(tag for item in public for tag in item.get("ai_type_tags") or [])
    generated_at = utc_now_iso()
    meta = {
        "schema_version": 1,
        "theme": "mh",
        "slug": "mental-health",
        "generated_at": generated_at,
        "status": status,
        "dry_run": dry_run,
        "model": model,
        "scope": "current_candidates_batch",
        "thresholds": thresholds,
        "totals": {
            "candidates_input": len(candidates),
            "papers_scored": len(scored),
            "papers_published": len(public),
            "failed": len(failures),
        },
        "facets": {
            "journals": dict(journal_counts.most_common()),
            "topic_tags": dict(topic_counts.most_common()),
            "ai_type_tags": dict(ai_type_counts.most_common()),
        },
    }
    report = {
        "schema_version": 1,
        "theme": "mh",
        "generated_at": generated_at,
        "status": status,
        "dry_run": dry_run,
        "limit_scope": "only the supplied current batch; no historical backlog safety valve",
        "model": model,
        "counts": meta["totals"],
        "usage": usage,
        "failures": failures,
    }
    _atomic_write_json(output_dir / "papers.json", public)
    _atomic_write_json(output_dir / "papers_full.json", full)
    _atomic_write_json(output_dir / "meta.json", meta)
    _atomic_write_json(output_dir / DEFAULT_SCORE_REPORT, report)
    return meta


def run_scoring(
    *,
    candidates: list[dict[str, Any]],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    config_path: str | Path | None = None,
    limit: int = 20,
    batch_size: int = 5,
    execute: bool = False,
    environ: Mapping[str, str] | None = None,
    client: MiniMaxScoringClient | Any | None = None,
) -> dict[str, Any]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    config = load_theme_config(config_path)
    selected = candidates[:limit]
    output_path = Path(output_dir)
    env = os.environ if environ is None else environ

    if not selected:
        return _write_exports(
            output_dir=output_path,
            candidates=selected,
            scored=[],
            config=config,
            status="empty_input",
            dry_run=not execute,
            model=None,
            failures=[],
            usage={},
        )
    if not execute:
        return _write_exports(
            output_dir=output_path,
            candidates=selected,
            scored=[],
            config=config,
            status="dry_run",
            dry_run=True,
            model=env.get("MINIMAX_MODEL", "MiniMax-M2.7"),
            failures=[],
            usage={},
        )

    owns_client = client is None
    active_client = client or MiniMaxScoringClient.from_environment(env)
    system_prompt = build_system_prompt(config)
    scored: list[tuple[dict[str, Any], dict[str, Any]]] = []
    failures: list[dict[str, Any]] = []
    total_usage: Counter[str] = Counter()
    try:
        for batch_start in range(0, len(selected), batch_size):
            batch = selected[batch_start : batch_start + batch_size]
            try:
                response = active_client.score_batch(batch, system_prompt)
                if isinstance(response, tuple):
                    raw_scores, usage = response
                else:
                    raw_scores, usage = response, {}
                total_usage.update({key: int(value or 0) for key, value in usage.items() if isinstance(value, (int, float))})
                raw_by_id = {str(item.get("id")): item for item in raw_scores}
                for candidate in batch:
                    candidate_id = str(candidate.get("id") or candidate.get("openalex_id") or "")
                    raw = raw_by_id.get(candidate_id)
                    if raw is None:
                        failures.append({"id": candidate_id, "error": "MiniMax omitted this candidate"})
                        continue
                    try:
                        scored.append((candidate, sanitize_score(raw, candidate, config)))
                    except ScoringContractError as exc:
                        failures.append({"id": candidate_id, "error": str(exc)})
            except Exception as exc:
                for candidate in batch:
                    failures.append(
                        {"id": candidate.get("id") or candidate.get("openalex_id"), "error": str(exc)}
                    )
    finally:
        if owns_client:
            active_client.close()

    status = "partial_failure" if failures else "success"
    return _write_exports(
        output_dir=output_path,
        candidates=selected,
        scored=scored,
        config=config,
        status=status,
        dry_run=False,
        model=getattr(active_client, "model", env.get("MINIMAX_MODEL", "MiniMax-M2.7")),
        failures=failures,
        usage=dict(total_usage),
    )
