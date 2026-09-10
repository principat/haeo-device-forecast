"""Live tracking of one device's current run, for the forecast sensors.

Implements the ``sleeping``/``running`` state machine from Specs.md
"Erkennen von Lastprofilen während der Nutzung": a run starts when power
crosses ``start_threshold`` and only ends once power has stayed at or below
that threshold for a duration derived from the longest known profile pause
(so an expected in-program pause is never mistaken for the run's end or an
abort). Whether a finished run completed cleanly or was cut short, it is
fed back into :func:`~.analysis.assign_run` the same way: even a partial
run is useful signal, either widening an existing profile's band over a
shorter prefix or, if unmatched, becoming the seed of a new one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .analysis import (
    assign_run,
    build_forecast_points,
    detect_profiles,
    detect_runs,
    match_live,
)
from .analysis import merge_profiles as merge_profile_bands
from .history import fetch_raw_history
from .models import DeviceRun, Profile, RawSample
from .storage import DeviceStore

_LOGGER = logging.getLogger(__name__)

STATUS_SLEEPING = "sleeping"
STATUS_RUNNING = "running"

#: End-of-run timeout used while no profile (and thus no learned pause
#: duration) is known yet for this device.
DEFAULT_END_TIMEOUT_SECONDS = 300.0
#: Safety margin added on top of the longest known profile pause, per
#: Specs.md ("... plus Sicherheitsmarge").
END_TIMEOUT_MARGIN_SECONDS = 60.0
#: Spacing of the HAEO ``forecast`` attribute's points (Specs.md: 5-Minuten-Raster).
FORECAST_GRID_SECONDS = 300
#: How far back to pull recorder history on the very first profile search,
#: per Specs.md "Analyse von Lastprofilen" (Basis: die letzten 30 Tage).
INITIAL_HISTORY_LOOKBACK_DAYS = 30


@dataclass(frozen=True, slots=True)
class DeviceForecastData:
    """Latest live-tracking snapshot exposed to the sensor entities.

    Attributes:
        status: ``"sleeping"`` or ``"running"``.
        profile_name: Name of the profile currently used for the forecast,
            or ``None`` while sleeping or with no known profiles.
        confidence_percent: DTW match confidence (0-100) for the current
            run against ``profile_name``, or ``None`` while sleeping.
        current_power: Latest raw power reading (W), or ``None`` if the
            source sensor is unavailable.
        estimated_end: Estimated wall-clock end time of the current run.
        forecast: HAEO ``forecast`` attribute payload: a list of
            ``{"time": <ISO-8601>, "value": <number>}`` points.
    """

    status: str
    profile_name: str | None
    confidence_percent: float | None
    current_power: float | None
    estimated_end: datetime | None
    forecast: list[dict[str, object]]


def _parse_power(state: State | None) -> float | None:
    """Parse a power sensor's state into a float, or ``None`` if not numeric."""
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


class DeviceForecastCoordinator(DataUpdateCoordinator[DeviceForecastData]):
    """Polls one device's power sensor and tracks its current run."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        subentry_id: str,
        device_name: str,
        power_entity_id: str,
        start_threshold: float,
        store: DeviceStore,
        bucket_seconds: int = 10,
        update_interval: timedelta = timedelta(seconds=30),
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance.
            config_entry: The (single, hub) config entry this coordinator's
                device is managed under.
            subentry_id: Id of the config subentry representing this device -
                its stable identity for storage keys, unique ids and the
                registered HA device (Specs.md: one hub entry manages
                multiple devices as config subentries).
            device_name: User-chosen name of this device, used as the HA
                device's display name.
            power_entity_id: Entity id of the device's power sensor.
            start_threshold: Power (W) above which a run is considered started.
            store: Long-term storage for this device's profiles/raw samples.
            bucket_seconds: Band bucket width in seconds, matching stored profiles.
            update_interval: How often to poll the power sensor.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"HAEO Device Forecast ({device_name})",
            update_interval=update_interval,
        )
        self.subentry_id = subentry_id
        self.device_name = device_name
        self.power_entity_id = power_entity_id
        self.start_threshold = start_threshold
        self.bucket_seconds = bucket_seconds
        self.profiles: list[Profile] = []
        self.status = STATUS_SLEEPING

        self._store = store
        self._current_run_samples: list[RawSample] = []
        self._run_started_at: datetime | None = None
        self._below_since: datetime | None = None

    async def async_load_profiles(self) -> None:
        """Load previously persisted profiles from storage."""
        self.profiles = await self._store.async_load_profiles()

    async def async_rename_profile(self, profile_id: str, name: str) -> None:
        """Rename one of this device's profiles (Dashboard/Pflege: Benennen).

        Args:
            profile_id: Id of the profile to rename.
            name: New, user-chosen name.

        Raises:
            ValueError: If no profile with ``profile_id`` is known.
        """
        if not any(profile.id == profile_id for profile in self.profiles):
            raise ValueError(f"Unknown profile id: {profile_id}")

        now = dt_util.utcnow()
        self.profiles = [
            replace(profile, name=name, updated_at=now) if profile.id == profile_id else profile
            for profile in self.profiles
        ]
        await self._store.async_save_profiles(self.profiles)
        self.async_update_listeners()

    async def async_merge_profiles(self, profile_ids: list[str], name: str) -> Profile:
        """Merge two or more of this device's profiles into one (Dashboard/Pflege: Mergen).

        Args:
            profile_ids: Ids of the profiles to merge (at least two).
            name: Name for the resulting merged profile.

        Returns:
            The newly created, merged profile.

        Raises:
            ValueError: If any id in ``profile_ids`` is unknown.
        """
        ids = set(profile_ids)
        to_merge = [profile for profile in self.profiles if profile.id in ids]
        if len(to_merge) != len(ids):
            raise ValueError("One or more profile ids not found")

        merged = merge_profile_bands(to_merge, name)
        self.profiles = [profile for profile in self.profiles if profile.id not in ids] + [merged]
        await self._store.async_save_profiles(self.profiles)
        self.async_update_listeners()
        return merged

    async def async_search_profiles(self) -> list[Profile]:
        """Re-run automatic profile discovery over the device's full raw-sample history.

        Per Specs.md "Analyse von Lastprofilen" (automatischer Modus, komplette
        30 Tage): pulls any recorder history not yet in our own long-term
        store - on the very first search that's up to
        :data:`INITIAL_HISTORY_LOOKBACK_DAYS`, afterwards just the gap since
        the newest stored sample - appends it to storage, then segments and
        clusters the combined history into profiles. Without this fetch,
        relying only on samples accumulated from completed live-tracking
        runs since setup would find nothing until a run had finished at
        least once.

        Returns:
            The newly discovered list of profiles (also stored on ``self.profiles``).
        """
        existing_samples = await self._store.async_load_raw_samples()
        now = dt_util.utcnow()
        since = (
            existing_samples[-1].timestamp
            if existing_samples
            else now - timedelta(days=INITIAL_HISTORY_LOOKBACK_DAYS)
        )

        new_samples = await fetch_raw_history(self.hass, self.power_entity_id, since, now)
        if existing_samples:
            new_samples = [s for s in new_samples if s.timestamp > existing_samples[-1].timestamp]
        if new_samples:
            await self._store.async_append_raw_samples(new_samples)

        all_samples = existing_samples + new_samples
        runs = detect_runs(all_samples, self.start_threshold, self._current_end_timeout_seconds())
        self.profiles = detect_profiles(runs, self.bucket_seconds, self.start_threshold)
        await self._store.async_save_profiles(self.profiles)
        self.async_update_listeners()
        return self.profiles

    def _current_end_timeout_seconds(self) -> float:
        """End-of-run timeout derived from known profiles' longest pause."""
        if not self.profiles:
            return DEFAULT_END_TIMEOUT_SECONDS
        longest_pause = max(profile.longest_pause_seconds() for profile in self.profiles)
        return longest_pause + END_TIMEOUT_MARGIN_SECONDS

    async def _async_update_data(self) -> DeviceForecastData:
        """Poll the power sensor once and advance the run state machine."""
        now = dt_util.utcnow()
        value = _parse_power(self.hass.states.get(self.power_entity_id))

        if value is not None:
            await self._advance_state_machine(now, value)

        return self._build_data(now)

    async def _advance_state_machine(self, now: datetime, value: float) -> None:
        """Update sleeping/running status for one new power reading."""
        sample = RawSample(timestamp=now, value=value)

        if self.status == STATUS_SLEEPING:
            if value > self.start_threshold:
                self.status = STATUS_RUNNING
                self._run_started_at = now
                self._current_run_samples = [sample]
                self._below_since = None
            return

        self._current_run_samples.append(sample)
        if value <= self.start_threshold:
            if self._below_since is None:
                self._below_since = now
            elif (now - self._below_since).total_seconds() >= self._current_end_timeout_seconds():
                await self._async_finish_run(self._below_since)
        else:
            self._below_since = None

    async def _async_finish_run(self, ended_at: datetime) -> None:
        """Close out the current run, learn a profile from it, and persist it."""
        samples = tuple(s for s in self._current_run_samples if s.timestamp <= ended_at)
        run = DeviceRun(started_at=self._run_started_at, ended_at=ended_at, samples=samples)

        profile, is_new = assign_run(run, self.profiles, self.bucket_seconds, self.start_threshold)
        if is_new:
            self.profiles = [*self.profiles, profile]
        else:
            self.profiles = [profile if p.id == profile.id else p for p in self.profiles]

        await self._store.async_save_profiles(self.profiles)
        await self._store.async_append_raw_samples(list(run.samples))

        self.status = STATUS_SLEEPING
        self._current_run_samples = []
        self._run_started_at = None
        self._below_since = None

    def _build_data(self, now: datetime) -> DeviceForecastData:
        """Compute the current sensor-facing snapshot."""
        current_power = self._current_run_samples[-1].value if self._current_run_samples else None

        if self.status == STATUS_SLEEPING or self._run_started_at is None:
            return DeviceForecastData(
                status=STATUS_SLEEPING,
                profile_name=None,
                confidence_percent=None,
                current_power=current_power,
                estimated_end=None,
                forecast=[],
            )

        match = match_live(self._current_run_samples, self.profiles, self.bucket_seconds)
        if match.profile is None:
            return DeviceForecastData(
                status=STATUS_RUNNING,
                profile_name=None,
                confidence_percent=None,
                current_power=current_power,
                estimated_end=None,
                forecast=[],
            )

        elapsed = (now - self._run_started_at).total_seconds()
        points = build_forecast_points(match.profile, elapsed, FORECAST_GRID_SECONDS)
        forecast = [
            {
                "time": (self._run_started_at + timedelta(seconds=offset)).isoformat(),
                "value": value,
            }
            for offset, value in points
        ]
        estimated_end = self._run_started_at + timedelta(seconds=match.profile.duration_seconds())

        return DeviceForecastData(
            status=STATUS_RUNNING,
            profile_name=match.profile.name,
            confidence_percent=match.confidence_percent,
            current_power=current_power,
            estimated_end=estimated_end,
            forecast=forecast,
        )
