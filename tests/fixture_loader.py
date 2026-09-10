"""Helper to load recorded real-world power-sensor fixtures for tests."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.util import dt as dt_util

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture_states(name: str) -> tuple[str, list[dict]]:
    """Load a fixture file's entity_id and raw state list.

    Args:
        name: Fixture file name (e.g. ``"geschirrspueler_run.json"``).

    Returns:
        A tuple of ``(entity_id, states)`` where ``states`` are the raw
        ``{"state": ..., "last_changed": ...}`` dicts as recorded.
    """
    with (FIXTURES_DIR / name).open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data["entity_id"], data["states"]


def fixture_timestamps(name: str) -> list[tuple[object, str]]:
    """Parse a fixture's states into (timestamp, state) pairs for convenience."""
    _, states = load_fixture_states(name)
    return [(dt_util.parse_datetime(s["last_changed"]), s["state"]) for s in states]
