"""Versioned, backup-safe persistence for one device's raw samples and profiles.

Uses :class:`homeassistant.helpers.storage.Store`, so data lands under
``.storage/`` in the HA config directory: automatically included in HA
Backups, removable in one call, and migratable between schema versions via
``_async_migrate_func``, per Specs.md "Technische Anforderungen".
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from ..models import Profile, RawSample

#: Bump when the raw-samples storage payload shape changes.
RAW_SAMPLES_STORAGE_VERSION = 1
#: Bump when the profiles storage payload shape changes.
PROFILES_STORAGE_VERSION = 1


class _RawSamplesStore(Store[dict[str, Any]]):
    """Store for one device's accumulated raw power samples."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate older raw-samples payloads to the current schema.

        No prior schema exists yet, so this is a no-op placeholder that
        future versions extend.
        """
        return old_data


class _ProfilesStore(Store[dict[str, Any]]):
    """Store for one device's list of recognized profiles."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate older profile-list payloads to the current schema.

        No prior schema exists yet, so this is a no-op placeholder that
        future versions extend.
        """
        return old_data


class DeviceStore:
    """Long-term storage of raw samples and profiles for one device.

    One instance manages exactly one device (one config subentry / power
    sensor). Raw samples are append-only and retained indefinitely so the
    30-day analysis window can grow beyond the recorder's own retention.
    """

    RAW_SAMPLES_VERSION = RAW_SAMPLES_STORAGE_VERSION
    PROFILES_VERSION = PROFILES_STORAGE_VERSION

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        """Initialize storage handles for a device.

        Args:
            hass: The Home Assistant instance.
            device_id: The id identifying the device (its config subentry id).
        """
        self.raw_samples_store = _RawSamplesStore(
            hass, RAW_SAMPLES_STORAGE_VERSION, f"{DOMAIN}_{device_id}_raw_samples"
        )
        self.profiles_store = _ProfilesStore(
            hass, PROFILES_STORAGE_VERSION, f"{DOMAIN}_{device_id}_profiles"
        )

    async def async_load_raw_samples(self) -> list[RawSample]:
        """Load all previously stored raw samples for this device."""
        data = await self.raw_samples_store.async_load()
        if data is None:
            return []
        return [RawSample.from_dict(item) for item in data["samples"]]

    async def async_append_raw_samples(self, new_samples: list[RawSample]) -> None:
        """Append newly fetched raw samples to the device's long-term history.

        Args:
            new_samples: Samples to add, in chronological order.
        """
        existing = await self.async_load_raw_samples()
        combined = existing + new_samples
        await self.raw_samples_store.async_save(
            {"samples": [sample.to_dict() for sample in combined]}
        )

    async def async_load_profiles(self) -> list[Profile]:
        """Load all recognized profiles for this device."""
        data = await self.profiles_store.async_load()
        if data is None:
            return []
        return [Profile.from_dict(item) for item in data["profiles"]]

    async def async_save_profiles(self, profiles: list[Profile]) -> None:
        """Replace the device's stored profile list.

        Args:
            profiles: The complete, new list of profiles to persist.
        """
        await self.profiles_store.async_save(
            {"profiles": [profile.to_dict() for profile in profiles]}
        )

    async def async_remove_all(self) -> None:
        """Permanently delete all stored data (raw samples and profiles) for this device."""
        await self.raw_samples_store.async_remove()
        await self.profiles_store.async_remove()
