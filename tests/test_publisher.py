from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import pytest
import yaml

from publisher.build_index import build_unified_index
from publisher.channel_registry import load_channel_registry
from publisher.git_source import read_git_json, sync_channel
from publisher.io_utils import write_json
from publisher.merge_channels import (
    merge_channel_records,
    merge_channel_records_with_diagnostics,
    normalize_channel_record,
)
from publisher.stable_id import canonical_key, stable_public_id
from publisher.update_pipeline import merge_mental_health_batch, sync_legacy_with_fallback
from publisher.validate_release import validate_release


def paper(**overrides):
    record = {
        "id": 12,
        "doi": "10.1234/Example.1",
        "title": "A Human-AI Study",
        "date": "2026-07-01",
        "year": 2026,
        "authors": ["Ada Lovelace"],
        "journal": "Example Journal",
        "ai_score": 5,
        "domain_score": 4,
        "topic_tags": ["trust"],
        "ai_type_tags": ["LLM"],
        "tldr": "Summary",
    }
    record.update(overrides)
    return record


def test_same_doi_merges_across_channels_and_preserves_profiles():
    ob = normalize_channel_record(paper(id=1), channel="ob", revision="ob-sha")
    ur = normalize_channel_record(
        paper(id=9, doi="https://doi.org/10.1234/EXAMPLE.1", domain_score=5, tldr="UR view"),
        channel="ur",
        revision="ur-sha",
    )

    result = merge_channel_records([ur, ob])

    assert len(result) == 1
    assert result[0]["channels"] == ["ob", "ur"]
    assert result[0]["channel_profiles"]["ob"]["domain_score"] == 4
    assert result[0]["channel_profiles"]["ur"]["tldr"] == "UR view"
    assert {(ref["channel"], ref["legacy_id"]) for ref in result[0]["source_refs"]} == {
        ("ob", 1),
        ("ur", 9),
    }


def test_public_id_is_stable_url_safe_and_independent_of_input_order():
    first = normalize_channel_record(paper(id=1), channel="ob")
    second = normalize_channel_record(paper(id=2, title_zh="中文标题"), channel="ur")

    forward = merge_channel_records([first, second])
    backward = merge_channel_records([second, first])

    assert forward == backward
    assert re.fullmatch(r"p_[A-Za-z0-9_-]{16}", forward[0]["id"])
    assert forward[0]["id"] == stable_public_id("doi:10.1234/example.1")


def test_no_doi_uses_normalized_title_year_first_author_fingerprint():
    left = paper(id=1, doi=None, title="Trust in Human–AI Teams!", authors=["Ada Lovelace"])
    right = paper(id=2, doi=None, title="  TRUST in human AI teams ", authors=["ADA LOVELACE"])

    assert canonical_key(left) == canonical_key(right)
    assert canonical_key(left).startswith("fingerprint:")
    assert len(merge_channel_records([
        normalize_channel_record(left, channel="ob"),
        normalize_channel_record(right, channel="ur"),
    ])) == 1


def test_arxiv_versions_share_one_key_when_doi_is_absent():
    left = paper(doi=None, url="https://arxiv.org/abs/2607.01234v1")
    right = paper(doi=None, url="https://arxiv.org/pdf/2607.01234v3")
    assert canonical_key(left) == canonical_key(right) == "arxiv:2607.01234"


def test_critical_mismatch_on_same_identifier_is_kept_and_reported():
    left = normalize_channel_record(paper(id=1), channel="ob")
    right = normalize_channel_record(
        paper(id=2, title="Completely unrelated clinical trial", year=2018, date="2018-01-01"),
        channel="ur",
    )

    merged, conflicts = merge_channel_records_with_diagnostics([right, left])

    assert len(merged) == 2
    assert len(conflicts) == 1
    assert conflicts[0]["canonical_key"] == "doi:10.1234/example.1"
    assert {item["title"] for item in merged} == {
        "A Human-AI Study",
        "Completely unrelated clinical trial",
    }


def test_merge_is_json_idempotent():
    records = [
        normalize_channel_record(paper(id=1), channel="ob", revision="abc"),
        normalize_channel_record(paper(id=2), channel="ur", revision="def"),
    ]
    first = json.dumps(merge_channel_records(records), ensure_ascii=False, sort_keys=True)
    second = json.dumps(merge_channel_records(reversed(records)), ensure_ascii=False, sort_keys=True)
    assert first == second


def test_missing_title_error_contains_source_context():
    with pytest.raises(ValueError, match=r"channel=mh, legacy_id=77"):
        normalize_channel_record(paper(id=77, title="", doi=None), channel="mh")


def _snapshot(path: Path, records: list[dict], *, generated_at: str, revision: str | None = None):
    write_json(path / "papers.json", records)
    write_json(
        path / "papers_full.json",
        [{**record, "abstract": f"Abstract {record['id']}"} for record in records],
    )
    write_json(path / "meta.json", {"generated_at": generated_at, "totals": {}})
    if revision:
        write_json(path / "_source.json", {"revision": revision, "generated_at": generated_at})


def test_build_supports_optional_mh_and_is_byte_idempotent(tmp_path: Path):
    upstream = tmp_path / "upstream"
    _snapshot(
        upstream / "ob",
        [paper(id=1), paper(id=3, doi="10.9999/old", title="Old", year=2022, date="2022-01-01")],
        generated_at="2026-07-01T00:00:00Z",
        revision="ob",
    )
    _snapshot(
        upstream / "ur",
        [paper(id=2, doi="10.9999/ur", title="UR only")],
        generated_at="2026-07-02T00:00:00Z",
        revision="ur",
    )
    mh_dir = upstream / "mh"
    _snapshot(
        mh_dir,
        [paper(id="mh-1", ai_relevance=5, domain_relevance=5)],
        generated_at="2026-07-03T00:00:00Z",
    )
    output = tmp_path / "public/data"
    report = tmp_path / "reports/unified.json"
    shared_id = stable_public_id("doi:10.1234/example.1")
    write_json(
        output / "papers" / f"{shared_id}.json",
        {"id": shared_id, "unified_ingested_at": "2025-01-01T00:00:00Z"},
    )

    built = build_unified_index(
        upstream_dir=upstream, output_dir=output, report_path=report
    )
    first_bytes = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*.json")}
    rebuilt = build_unified_index(
        upstream_dir=upstream, output_dir=output, report_path=report
    )
    second_bytes = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*.json")}

    assert built == rebuilt
    assert first_bytes == second_bytes
    assert built["pending_channels"] == []
    assert built["counts"]["excluded_before_start_year"] == 1
    assert built["excluded_before_start_year"][0]["legacy_id"] == 3
    merged = json.loads((output / "papers.json").read_text())
    assert all((item["year"] or 9999) >= 2023 for item in merged)
    shared = next(item for item in merged if item["id"] == shared_id)
    assert shared["channels"] == ["mh", "ob"]
    assert shared["channel_profiles"]["mh"]["ai_score"] == 5
    assert set(shared["channel_profiles"]["mh"]) == {
        "ai_score", "domain_score", "topic_tags", "tldr"
    }
    assert "doi" not in shared and "source_refs" not in shared
    detail = json.loads((output / "papers" / f"{shared['id']}.json").read_text())
    assert detail["doi"] == "10.1234/example.1"
    assert detail["source_refs"]
    meta = json.loads((output / "meta.json").read_text())
    assert meta["generated_at"] == meta["built_at"]
    assert meta["upstream_generated_at"] == "2026-07-03T00:00:00Z"
    rss = ElementTree.parse(output.parent / "rss.xml")
    items = rss.findall("./channel/item")
    assert len(items) == min(len(merged), 30)
    published = [parsedate_to_datetime(item.findtext("pubDate")) for item in items]
    assert published == sorted(published, reverse=True)
    assert all("/papers/p_" in item.findtext("guid", "") for item in items)
    assert items[-1].findtext("guid", "").endswith(shared_id)


def test_channel_registry_can_publish_a_fourth_channel_without_code_changes(tmp_path: Path):
    upstream = tmp_path / "upstream"
    for channel in ("ob", "ur", "mh", "edu"):
        _snapshot(
            upstream / channel,
            [paper(id=f"{channel}-1", doi=f"10.9999/{channel}", title=f"{channel} paper")],
            generated_at="2026-07-03T00:00:00Z",
            revision=channel,
        )
    channels = [
        {
            "id": channel,
            "short": channel.upper(),
            "label": f"{channel} label",
            "description": f"{channel} description",
            "color": "#345678",
            "soft_color": "#e8eef2",
            "order": index * 10,
            "required": channel in {"ob", "ur"},
            "data_dir": str(upstream / channel),
            "source_kind": "native",
        }
        for index, channel in enumerate(("ob", "ur", "mh", "edu"), start=1)
    ]
    registry = tmp_path / "channels.yaml"
    registry.write_text(yaml.safe_dump({"schema_version": 1, "channels": channels}), encoding="utf-8")
    output = tmp_path / "public/data"
    report = tmp_path / "reports/unified.json"

    build_unified_index(
        upstream_dir=upstream,
        output_dir=output,
        report_path=report,
        registry_path=registry,
    )
    meta = json.loads((output / "meta.json").read_text())

    assert [definition.id for definition in load_channel_registry(registry)] == ["ob", "ur", "mh", "edu"]
    assert meta["channels"]["edu"]["label"] == "edu label"
    assert meta["channels"]["edu"]["papers"] == 1
    checked = validate_release(
        output_dir=output,
        report_path=report,
        rss_path=output.parent / "rss.xml",
    )
    assert checked["channels"]["edu"] == 1


def _init_git_publication(repo: Path):
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "Test"], check=True)
    data = repo / "web/public/data"
    write_json(data / "papers.json", [paper(title="Committed")])
    write_json(data / "papers_full.json", [paper(title="Committed")])
    write_json(data / "meta.json", {"generated_at": "2026-07-01T00:00:00Z"})
    subprocess.run(["git", "-C", repo, "add", "."], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "fixture"], check=True)


def test_git_sync_reads_revision_not_dirty_worktree(tmp_path: Path):
    repo = tmp_path / "legacy"
    _init_git_publication(repo)
    write_json(repo / "web/public/data/papers.json", [paper(title="Dirty")])

    source = sync_channel(repo, "HEAD", "ob", tmp_path / "upstream")
    synced = json.loads((tmp_path / "upstream/ob/papers.json").read_text())

    assert synced[0]["title"] == "Committed"
    assert source["revision"] == subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "HEAD"], text=True
    ).strip()


def test_git_read_error_names_repo_revision_and_file(tmp_path: Path):
    repo = tmp_path / "legacy"
    _init_git_publication(repo)
    revision = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "HEAD"], text=True
    ).strip()
    with pytest.raises(RuntimeError) as error:
        read_git_json(repo, revision, "web/public/data/missing.json")
    message = str(error.value)
    assert str(repo) in message
    assert revision in message
    assert "missing.json" in message


def test_failure_aware_sync_keeps_previous_valid_channel_snapshot(tmp_path: Path):
    ob = tmp_path / "ob"
    ur = tmp_path / "ur"
    _init_git_publication(ob)
    _init_git_publication(ur)
    output = tmp_path / "upstream"
    sync_legacy_with_fallback(
        ob_repo=ob, ur_repo=ur, ob_ref="HEAD", ur_ref="HEAD", output_dir=output
    )

    manifest = sync_legacy_with_fallback(
        ob_repo=ob, ur_repo=ur, ob_ref="missing-ref", ur_ref="HEAD", output_dir=output
    )

    assert manifest["stale_channels"] == ["ob"]
    assert manifest["failures"][0]["fallback"] == "previous_valid_snapshot"
    assert json.loads((output / "ob/papers.json").read_text())[0]["title"] == "Committed"


def test_executed_mental_health_batch_merges_into_cumulative_snapshot(tmp_path: Path):
    batch = tmp_path / "batch"
    cumulative = tmp_path / "cumulative"
    existing = paper(id="W1", doi="10.9999/existing", title="Existing")
    incoming = paper(id="W2", doi="10.9999/incoming", title="Incoming")
    for directory, records in ((cumulative, [existing]), (batch, [incoming])):
        write_json(directory / "papers.json", records)
        write_json(directory / "papers_full.json", records)
    write_json(cumulative / "meta.json", {"generated_at": "2026-07-01", "dry_run": False})
    write_json(
        batch / "meta.json",
        {"generated_at": "2026-07-02", "dry_run": False, "status": "success", "totals": {"papers_published": 1}},
    )

    result = merge_mental_health_batch(batch_dir=batch, cumulative_dir=cumulative)

    assert result["previous_papers"] == 1
    assert result["cumulative_papers"] == 2
    assert len(json.loads((cumulative / "papers.json").read_text())) == 2
