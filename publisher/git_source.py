"""Read immutable publication assets from upstream Git revisions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .io_utils import write_json


PUBLISH_FILES = ("papers.json", "papers_full.json", "meta.json")


def _git(repo: Path, *arguments: str, context: str) -> str:
    command = ["git", "-C", str(repo), *arguments]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"{context}: failed to start git for {repo}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{context}: git command failed in {repo}: {detail}")
    return result.stdout


def resolve_revision(repo: Path, ref: str) -> str:
    return _git(
        repo,
        "rev-parse",
        "--verify",
        f"{ref}^{{commit}}",
        context=f"resolve revision ref={ref}",
    ).strip()


def read_git_json(repo: Path, revision: str, relative_path: str) -> tuple[Any, bytes]:
    context = f"read formal publication repo={repo} revision={revision} file={relative_path}"
    raw = _git(repo, "show", f"{revision}:{relative_path}", context=context).encode("utf-8")
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{context}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def sync_channel(repo: Path, ref: str, channel: str, output_dir: Path) -> dict[str, Any]:
    revision = resolve_revision(repo, ref)
    files: dict[str, Any] = {}
    checksums: dict[str, str] = {}
    for filename in PUBLISH_FILES:
        relative_path = f"web/public/data/{filename}"
        value, raw = read_git_json(repo, revision, relative_path)
        files[filename] = value
        checksums[filename] = hashlib.sha256(raw).hexdigest()

    if not isinstance(files["papers.json"], list):
        raise RuntimeError(f"sync channel={channel} revision={revision}: papers.json must be an array")
    if not isinstance(files["papers_full.json"], list):
        raise RuntimeError(f"sync channel={channel} revision={revision}: papers_full.json must be an array")
    if not isinstance(files["meta.json"], dict):
        raise RuntimeError(f"sync channel={channel} revision={revision}: meta.json must be an object")

    channel_dir = output_dir / channel
    for filename, value in files.items():
        write_json(channel_dir / filename, value)
    source = {
        "channel": channel,
        "ref": ref,
        "revision": revision,
        "repo": str(repo.resolve()),
        "generated_at": files["meta.json"].get("generated_at"),
        "files": checksums,
    }
    write_json(channel_dir / "_source.json", source)
    return source


def sync_legacy_sources(
    *,
    ob_repo: Path,
    ur_repo: Path,
    ob_ref: str,
    ur_ref: str,
    output_dir: Path,
) -> dict[str, Any]:
    sources = {
        "ob": sync_channel(ob_repo, ob_ref, "ob", output_dir),
        "ur": sync_channel(ur_repo, ur_ref, "ur", output_dir),
    }
    manifest = {"schema_version": 1, "channels": sources}
    write_json(output_dir / "manifest.json", manifest)
    return manifest
