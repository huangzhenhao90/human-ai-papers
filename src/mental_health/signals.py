"""Deterministic recall gate used before paid scoring."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize(text: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", text or "").casefold().split())


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(_normalize(term)).replace(r"\ ", r"\s+")
    prefix = r"(?<!\w)" if term[:1].isalnum() else ""
    suffix = r"(?!\w)" if term[-1:].isalnum() else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


def matching_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _term_pattern(str(term)).search(text)]


def match_false_positive_rules(text: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = _normalize(text)
    matched: list[dict[str, Any]] = []
    for rule in config.get("false_positive_rules") or []:
        patterns = rule.get("patterns") or []
        if not any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
            continue
        unless_terms = [str(term) for term in rule.get("unless_terms") or []]
        if matching_terms(normalized, unless_terms):
            continue
        matched.append(
            {
                "id": rule.get("id"),
                "description": rule.get("description"),
                "max_domain_score": int(rule.get("max_domain_score", 2)),
            }
        )
    return matched


def evaluate_recall(title: str | None, abstract: str | None, config: dict[str, Any]) -> dict[str, Any]:
    text = _normalize(f"{title or ''}\n{abstract or ''}")
    recall = config.get("recall") or {}
    ai_terms = matching_terms(text, ((recall.get("ai_signal") or {}).get("terms") or []))
    mh_terms = matching_terms(text, ((recall.get("mental_health_signal") or {}).get("terms") or []))
    false_positive_matches = match_false_positive_rules(text, config)
    dual_signal = bool(ai_terms and mh_terms)
    return {
        "expression": "AI_SIGNAL AND MENTAL_HEALTH_SIGNAL",
        "ai_signal": bool(ai_terms),
        "mental_health_signal": bool(mh_terms),
        "ai_matches": ai_terms,
        "mental_health_matches": mh_terms,
        "false_positive_matches": false_positive_matches,
        "eligible": bool(dual_signal and not false_positive_matches),
    }


def false_positive_domain_cap(decision: dict[str, Any]) -> int | None:
    caps = [item["max_domain_score"] for item in decision.get("false_positive_matches") or []]
    return min(caps) if caps else None
