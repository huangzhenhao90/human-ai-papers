"""Unified publication contract for AI Papers."""

from .merge_channels import merge_channel_records
from .stable_id import canonical_key, stable_public_id

__all__ = ["canonical_key", "merge_channel_records", "stable_public_id"]
