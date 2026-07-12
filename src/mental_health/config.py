"""Configuration loading and source-identifier validation for the MH theme."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "themes" / "mental-health.yaml"
OPENALEX_ID_RE = re.compile(r"^S\d+$")


class ConfigError(ValueError):
    """Raised when the mental-health theme configuration is not usable."""


def load_theme_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigError(f"Mental-health config does not exist: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Mental-health config must be a mapping: {config_path}")

    required = ("theme", "sources", "recall", "controlled_tags")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ConfigError(f"Mental-health config is missing: {', '.join(missing)}")
    if raw["theme"].get("id") != "mh":
        raise ConfigError("theme.id must be 'mh'")
    if raw["recall"].get("query_expression") != "AI_SIGNAL AND MENTAL_HEALTH_SIGNAL":
        raise ConfigError("recall.query_expression must enforce both signals")

    for source in iter_sources(raw):
        if source.get("ingest_mode") not in {"full", "query"}:
            raise ConfigError(f"Source {source.get('key')!r} has invalid ingest_mode")
    return raw


def iter_sources(config: dict[str, Any]) -> Iterable[dict[str, Any]]:
    sources = config.get("sources") or {}
    for layer_name in ("full", "query"):
        for source in (sources.get(layer_name) or {}).get("journals") or []:
            yield {**source, "source_layer": layer_name, "source_type": "journal"}
    for source in (sources.get("conferences") or {}).get("items") or []:
        yield {**source, "source_layer": "conferences", "source_type": "conference"}
    arxiv = sources.get("arxiv")
    if isinstance(arxiv, dict):
        yield {**arxiv, "source_layer": "arxiv", "source_type": "repository"}


def normalize_openalex_source_id(value: Any) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().rstrip("/").rsplit("/", 1)[-1].upper()
    return normalized if OPENALEX_ID_RE.fullmatch(normalized) else None


def validate_source_identifiers(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a machine-readable audit; missing IDs are explicit, never guessed."""
    results: list[dict[str, Any]] = []
    for source in iter_sources(config):
        raw_id = source.get("openalex_id")
        normalized_id = normalize_openalex_source_id(raw_id)
        issues: list[str] = []
        if not raw_id:
            issues.append("missing_openalex_id")
        elif not normalized_id:
            issues.append("invalid_openalex_id")
        if source["source_type"] == "journal" and not source.get("issn_l"):
            issues.append("missing_issn_l")
        results.append(
            {
                "key": source.get("key"),
                "name": source.get("name"),
                "source_layer": source["source_layer"],
                "source_type": source["source_type"],
                "ingest_mode": source.get("ingest_mode"),
                "openalex_id": normalized_id,
                "issn_l": source.get("issn_l"),
                "status": "verified_in_config" if not issues else "needs_runtime_resolution",
                "issues": issues,
            }
        )
    return results
