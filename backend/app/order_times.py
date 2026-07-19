"""Canonical order timestamps used by backend integrations."""

from typing import Optional


def effective_harvested_at(harvested_at: Optional[str], created_at: str) -> str:
    """Use the supplied harvest time, or the order creation time as fallback."""
    if isinstance(harvested_at, str) and harvested_at.strip():
        return harvested_at.strip()
    return created_at
