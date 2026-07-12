"""Deterministic and failure-safe JSON file helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def read_json(path: Path, *, context: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"{context}: file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{context}: invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"{context}: cannot read {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> bool:
    """Atomically write deterministic JSON; return whether bytes changed."""

    return write_bytes(path, json_bytes(value))


def write_bytes(path: Path, payload: bytes) -> bool:
    """Atomically write bytes; return whether the file changed."""

    try:
        if path.read_bytes() == payload:
            return False
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return True


def replace_json_directory(path: Path, documents: dict[str, Any]) -> bool:
    """Replace a directory of JSON documents while removing stale files."""

    expected = {f"{name}.json": json_bytes(value) for name, value in documents.items()}
    if path.is_dir():
        current_names = {item.name for item in path.iterdir() if item.is_file()}
        if current_names == set(expected):
            if all((path / name).read_bytes() == payload for name, payload in expected.items()):
                return False

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(tempfile.mkdtemp(prefix=f".{path.name}.", dir=path.parent))
    backup_path = path.with_name(f".{path.name}.previous")
    try:
        for name, payload in expected.items():
            (temporary_path / name).write_bytes(payload)
        if backup_path.exists():
            shutil.rmtree(backup_path)
        if path.exists():
            os.replace(path, backup_path)
        os.replace(temporary_path, path)
        if backup_path.exists():
            shutil.rmtree(backup_path)
    except Exception:
        if not path.exists() and backup_path.exists():
            os.replace(backup_path, path)
        shutil.rmtree(temporary_path, ignore_errors=True)
        raise
    return True
