from __future__ import annotations

import json
from pathlib import Path

import pytest

from publisher.normalize_contract import load_channel_snapshot
from src.mental_health.config import load_theme_config, validate_source_identifiers
from src.mental_health.openalex import run_fetch
from src.mental_health.scoring import MissingAPIKeyError, run_scoring
from src.mental_health.signals import evaluate_recall


def candidate(
    *,
    paper_id: str = "W123",
    title: str = "Large language models for depression screening",
    abstract: str = "We validate an AI screening model for depression in a clinical sample.",
) -> dict:
    return {
        "id": paper_id,
        "openalex_id": paper_id,
        "doi": "10.1234/mh.1",
        "title": title,
        "abstract": abstract,
        "publication_date": "2026-07-01",
        "publication_year": 2026,
        "authors": ["A. Researcher"],
        "journal": "JMIR Mental Health",
        "source_key": "jmir_mental_health",
        "source_id": "S2764449704",
        "source_layer": "full",
        "source_type": "journal",
        "ingest_mode": "full",
        "url": "https://doi.org/10.1234/mh.1",
        "pdf_url": None,
        "cited_by": 2,
    }


def raw_score(paper_id: str = "W123", *, domain: int = 5) -> dict:
    return {
        "id": paper_id,
        "ai_relevance": 5,
        "domain_relevance": domain,
        "rationale_zh": "AI用于抑郁筛查并含临床验证",
        "title_zh": "用于抑郁筛查的大语言模型",
        "tldr_zh": "研究在临床样本中回顾性验证AI抑郁筛查。",
        "evidence_stage": "retrospective_validation",
        "clinical_validation": "internal",
        "safety_evaluated": False,
        "real_world_deployment": False,
        "ground_truth_quality": "validated_instrument",
        "evidence": {
            "study_design": "retrospective validation",
            "sample": "clinical sample",
            "outcomes": "screening accuracy",
        },
        "controlled_tags": {
            "conditions": ["depression", "invented_condition"],
            "applications": ["screening_assessment"],
            "populations": ["clinical_patients"],
            "ai_types": ["llm_genai"],
            "risks": ["bias_fairness"],
        },
    }


class FakeScoringClient:
    model = "fake-no-network"

    def score_batch(self, papers: list[dict], system_prompt: str):
        assert "ai_relevance >= 3 AND domain_relevance >= 3" in system_prompt
        return [raw_score(str(paper["id"])) for paper in papers], {"prompt_tokens": 10, "completion_tokens": 20}


class FakeOpenAlexClient:
    def resolve_source(self, name: str, issn_l: str | None = None):
        return {"openalex_id": "S999", "resolution": "runtime_exact_name"}

    def fetch_works(self, *, source_id, from_date, to_date, limit, search=None):
        relevant = source_id == "S4387286578"
        title = (
            "Large language models for depression screening"
            if relevant
            else "Unrelated longitudinal cohort report"
        )
        identifier = "W_RELEVANT" if relevant else f"W_{source_id}_{search or 'full'}"
        return [
            {
                "id": f"https://openalex.org/{identifier}",
                "title": title,
                "publication_date": "2024-01-01" if relevant else "2026-07-01",
                "publication_year": 2024 if relevant else 2026,
                "authorships": [],
                "primary_location": {"source": {"id": f"https://openalex.org/{source_id}"}},
            }
        ]


def test_config_loads_layers_signals_and_identifier_audit():
    config = load_theme_config()
    assert config["theme"]["id"] == "mh"
    assert config["sources"]["full"]["journals"]
    assert config["sources"]["query"]["query_expression"] == "AI_SIGNAL AND MENTAL_HEALTH_SIGNAL"
    assert config["sources"]["arxiv"]["categories"] == [
        "cs.CL",
        "cs.HC",
        "cs.AI",
        "cs.LG",
        "cs.CY",
        "cs.SI",
        "stat.ML",
        "eess.AS",
    ]
    audit = validate_source_identifiers(config)
    verified = next(item for item in audit if item["key"] == "nature_mental_health")
    unresolved = next(item for item in audit if item["key"] == "nejm_ai")
    assert verified["openalex_id"] == "S4387286578"
    assert verified["status"] == "verified_in_config"
    assert unresolved["openalex_id"] is None
    assert "missing_openalex_id" in unresolved["issues"]


@pytest.mark.parametrize(
    ("title", "abstract", "ai", "mental_health", "eligible"),
    [
        ("Large language models for depression screening", "Clinical assessment study", True, True, True),
        ("Large language models for code generation", "Software benchmark", True, False, False),
        ("Depression among adolescents", "Prevalence survey", False, True, False),
    ],
)
def test_dual_signal_recall_gate(title, abstract, ai, mental_health, eligible):
    decision = evaluate_recall(title, abstract, load_theme_config())
    assert decision["ai_signal"] is ai
    assert decision["mental_health_signal"] is mental_health
    assert decision["eligible"] is eligible


def test_false_positive_rules_block_wording_only_recall():
    decision = evaluate_recall(
        "Stress testing large language models for hallucination",
        "A production engineering benchmark for AI systems.",
        load_theme_config(),
    )
    assert decision["ai_signal"] is True
    assert decision["mental_health_signal"] is True
    assert decision["eligible"] is False
    assert {item["id"] for item in decision["false_positive_matches"]} == {
        "technical_stress_testing",
        "llm_hallucination_only",
    }


def test_fetch_dry_run_writes_empty_candidates_and_validation_report(tmp_path: Path):
    output = tmp_path / "candidates.json"
    report_path = tmp_path / "fetch_report.json"
    candidates, report = run_fetch(
        candidates_path=output,
        report_path=report_path,
        limit=7,
        dry_run=True,
    )
    assert candidates == []
    assert json.loads(output.read_text()) == []
    saved_report = json.loads(report_path.read_text())
    assert report["status"] == saved_report["status"] == "dry_run"
    assert saved_report["parameters"]["limit"] == 7
    assert any(item["status"] == "needs_runtime_resolution" for item in saved_report["source_validation"])


def test_bounded_fetch_prioritizes_dual_signal_full_source_candidate(tmp_path: Path):
    candidates, report = run_fetch(
        candidates_path=tmp_path / "candidates.json",
        report_path=tmp_path / "fetch_report.json",
        limit=1,
        client=FakeOpenAlexClient(),
    )
    assert report["status"] == "success"
    assert len(candidates) == 1
    assert candidates[0]["id"] == "W_RELEVANT"
    assert candidates[0]["recall"]["eligible"] is True


def test_execute_with_nonempty_input_requires_key(tmp_path: Path):
    with pytest.raises(MissingAPIKeyError, match="MINIMAX_API_KEY"):
        run_scoring(
            candidates=[candidate()],
            output_dir=tmp_path,
            execute=True,
            environ={},
        )


def test_empty_input_needs_no_key_and_writes_contract(tmp_path: Path):
    meta = run_scoring(
        candidates=[],
        output_dir=tmp_path,
        execute=True,
        environ={},
    )
    assert meta["status"] == "empty_input"
    assert json.loads((tmp_path / "papers.json").read_text()) == []
    assert json.loads((tmp_path / "papers_full.json").read_text()) == []
    saved_meta = json.loads((tmp_path / "meta.json").read_text())
    assert saved_meta["totals"] == {
        "candidates_input": 0,
        "papers_scored": 0,
        "papers_published": 0,
        "failed": 0,
    }


def test_fake_score_exports_publisher_contract_and_controlled_tags(tmp_path: Path):
    meta = run_scoring(
        candidates=[candidate()],
        output_dir=tmp_path,
        execute=True,
        client=FakeScoringClient(),
    )
    assert meta["status"] == "success"
    assert meta["totals"]["papers_published"] == 1
    assert meta["processed_candidate_keys"] == ["doi:10.1234/mh.1"]
    papers = json.loads((tmp_path / "papers.json").read_text())
    full = json.loads((tmp_path / "papers_full.json").read_text())
    assert set(papers[0]) >= {
        "id",
        "title",
        "title_zh",
        "date",
        "authors",
        "ai_score",
        "domain_score",
        "topic_tags",
        "ai_type_tags",
        "evidence_stage",
        "risk_tags",
    }
    assert "invented_condition" not in papers[0]["topic_tags"]
    assert full[0]["mh_profile"]["evidence"]["study_design"] == "retrospective validation"
    snapshot = load_channel_snapshot(tmp_path, "mh")
    assert snapshot.diagnostics["normalized"] == 1
    assert snapshot.records[0]["domain_score"] == 5


def test_false_positive_caps_domain_and_prevents_publication(tmp_path: Path):
    false_recall = candidate(
        title="Stress testing large language models for hallucination",
        abstract="A production engineering benchmark for AI systems.",
    )
    meta = run_scoring(
        candidates=[false_recall],
        output_dir=tmp_path,
        execute=True,
        client=FakeScoringClient(),
    )
    assert meta["totals"]["papers_scored"] == 1
    assert meta["totals"]["papers_published"] == 0
    assert json.loads((tmp_path / "papers.json").read_text()) == []
