"""Load and validate the single source of truth for published channels."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


CHANNEL_ID = re.compile(r"[a-z][a-z0-9-]{0,31}")
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class ChannelDefinition:
    id: str
    short: str
    label: str
    description: str
    color: str
    soft_color: str
    order: int
    required: bool
    data_dir: str
    source_kind: str

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("data_dir")
        value.pop("source_kind")
        return value


def default_registry_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config/channels.yaml"


def load_channel_registry(path: Path | None = None) -> list[ChannelDefinition]:
    registry_path = path or default_registry_path()
    try:
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"channel registry: cannot read {registry_path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeError("channel registry: schema_version must be 1")
    rows = payload.get("channels")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("channel registry: channels must be a non-empty array")

    definitions: list[ChannelDefinition] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"channel registry: channels[{index}] must be an object")
        try:
            definition = ChannelDefinition(
                id=str(row["id"]),
                short=str(row["short"]),
                label=str(row["label"]),
                description=str(row["description"]),
                color=str(row["color"]),
                soft_color=str(row["soft_color"]),
                order=int(row["order"]),
                required=bool(row["required"]),
                data_dir=str(row["data_dir"]),
                source_kind=str(row["source_kind"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"channel registry: invalid channels[{index}]: {exc}") from exc
        if not CHANNEL_ID.fullmatch(definition.id):
            raise RuntimeError(f"channel registry: invalid id={definition.id!r}")
        if not definition.short.strip() or not definition.label.strip():
            raise RuntimeError(f"channel registry: id={definition.id} requires short and label")
        if not HEX_COLOR.fullmatch(definition.color) or not HEX_COLOR.fullmatch(definition.soft_color):
            raise RuntimeError(f"channel registry: id={definition.id} colors must be six-digit hex")
        definitions.append(definition)

    ids = [definition.id for definition in definitions]
    orders = [definition.order for definition in definitions]
    if len(ids) != len(set(ids)):
        raise RuntimeError("channel registry: channel ids must be unique")
    if len(orders) != len(set(orders)):
        raise RuntimeError("channel registry: channel order values must be unique")
    return sorted(definitions, key=lambda definition: (definition.order, definition.id))


def resolve_channel_data_dir(
    definition: ChannelDefinition, *, project_root: Path, upstream_dir: Path
) -> Path:
    configured = Path(definition.data_dir)
    if not configured.is_absolute():
        configured = project_root / configured
    legacy_override = upstream_dir / definition.id
    if definition.source_kind == "legacy_git":
        return legacy_override
    return configured
