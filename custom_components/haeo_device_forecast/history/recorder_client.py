"""Access to Home Assistant's raw recorder history for a power sensor.

Deliberately uses the raw ``states`` table (via
:func:`homeassistant.components.recorder.history.state_changes_during_period`)
rather than the recorder's long-term statistics tables, so pattern
recognition works at full measurement resolution instead of being limited
by an aggregation interval, per Specs.md "Analyse von Lastprofilen".
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.recorder import get_instance, history
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from ..models import RawSample

_IGNORED_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}


def _states_to_samples(states: list[State]) -> list[RawSample]:
    """Convert recorder ``State`` rows to numeric samples, dropping non-numeric ones."""
    samples: list[RawSample] = []
    for state in states:
        if state.state in _IGNORED_STATES:
            continue
        try:
            value = float(state.state)
        except ValueError:
            continue
        samples.append(RawSample(timestamp=state.last_changed, value=value))
    return samples


async def fetch_raw_history(
    hass: HomeAssistant, entity_id: str, start: datetime, end: datetime
) -> list[RawSample]:
    """Fetch raw power readings for one entity over a time range.

    Args:
        hass: The Home Assistant instance.
        entity_id: The power sensor entity to read history for.
        start: Start of the time range (inclusive).
        end: End of the time range (inclusive).

    Returns:
        Numeric samples in chronological order. States that are
        ``unavailable``, ``unknown``, or otherwise not parseable as a
        number are skipped (measurement dropouts, per Specs.md).
    """
    states_by_entity = await get_instance(hass).async_add_executor_job(
        history.state_changes_during_period,
        hass,
        start,
        end,
        entity_id,
        True,  # no_attributes
        False,  # descending
        None,  # limit
        False,  # include_start_time_state
    )
    return _states_to_samples(states_by_entity.get(entity_id, []))
