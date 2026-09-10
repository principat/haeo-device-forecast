"""Group device runs into profiles: matching, creation, and merging.

Per Specs.md "Analyse von Lastprofilen": whether a recorded run belongs to
an existing profile or starts a new one is decided automatically, tolerant
to measurement noise and small time shifts (handled by the band-aware DTW
confidence in :mod:`.dtw`). A matching run widens the profile's band
(min/max) to also cover its own values, so the profile "learns" its own
tolerance from observed runs, in addition to the fixed guideline
tolerances from Specs.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from ..models import BandBucket, DeviceRun, Profile, RawSample
from .banding import build_band
from .dtw import CONFIDENCE_MATCH_THRESHOLD, band_aware_dtw_cost, confidence_percent

#: Extra profile buckets considered beyond the live/run length, to give the
#: DTW window room to align a slightly longer or shorter run.
_MATCH_LOOKAHEAD_BUCKETS = 3


def _run_end(run: DeviceRun) -> datetime:
    """Effective end timestamp of a run for banding purposes."""
    if run.ended_at is not None:
        return run.ended_at
    return run.samples[-1].timestamp


def _detect_pause_windows(
    buckets: tuple[BandBucket, ...], pause_threshold: float
) -> tuple[tuple[int, int], ...]:
    """Find contiguous low-power stretches within a run's buckets.

    A pause is any interior stretch of buckets whose mean power stays at or
    below ``pause_threshold`` - the same threshold used to detect a run's
    start/end (Specs.md: a program-internal pause has "geringen, aber von
    null verschiedenen Verbrauch").
    """
    if len(buckets) < 3:
        return ()

    windows: list[tuple[int, int]] = []
    pause_start: int | None = None
    # Skip the first and last bucket: those border run start/end, not an
    # in-program pause.
    for bucket in buckets[1:-1]:
        if bucket.mean <= pause_threshold:
            if pause_start is None:
                pause_start = bucket.offset_seconds
        elif pause_start is not None:
            windows.append((pause_start, bucket.offset_seconds))
            pause_start = None
    if pause_start is not None:
        windows.append((pause_start, buckets[-1].offset_seconds))
    return tuple(windows)


def create_profile_from_run(run: DeviceRun, bucket_seconds: int, pause_threshold: float) -> Profile:
    """Create a new, generically-named profile from a single observed run.

    Args:
        run: The finished run to learn a profile from.
        bucket_seconds: Band bucket width in seconds (Richtwert 5-10s).
        pause_threshold: Power (W) below which a bucket counts as an
            in-program pause rather than active operation.

    Returns:
        A new :class:`Profile` with a generic, user-renameable name.
    """
    buckets = tuple(build_band(list(run.samples), bucket_seconds, end=_run_end(run)))
    now = datetime.now(timezone.utc)
    return Profile(
        id=str(uuid4()),
        name=f"Profil {now.strftime('%Y-%m-%d %H:%M')}",
        buckets=buckets,
        pause_windows=_detect_pause_windows(buckets, pause_threshold),
        created_at=now,
        updated_at=now,
    )


def _widen_bucket(existing: BandBucket, observed: BandBucket) -> BandBucket:
    """Widen one bucket's band to also cover an observed bucket's range."""
    return BandBucket(
        offset_seconds=existing.offset_seconds,
        min=min(existing.min, observed.min),
        mean=(existing.mean + observed.mean) / 2,
        max=max(existing.max, observed.max),
    )


def merge_run_into_profile(profile: Profile, run: DeviceRun, bucket_seconds: int) -> Profile:
    """Widen a profile's band to also cover a newly matched run.

    Args:
        profile: The existing profile the run was matched to.
        run: The run to fold into the profile's band.
        bucket_seconds: Band bucket width in seconds, matching ``profile``.

    Returns:
        An updated copy of ``profile`` with a widened band and bumped
        ``updated_at``; buckets beyond the run's own length are kept as-is.
    """
    run_buckets = build_band(list(run.samples), bucket_seconds, end=_run_end(run))
    widened = tuple(
        _widen_bucket(existing, run_buckets[i]) if i < len(run_buckets) else existing
        for i, existing in enumerate(profile.buckets)
    )
    return Profile(
        id=profile.id,
        name=profile.name,
        buckets=widened,
        pause_windows=profile.pause_windows,
        created_at=profile.created_at,
        updated_at=datetime.now(timezone.utc),
        schema_version=profile.schema_version,
    )


def assign_run(
    run: DeviceRun,
    profiles: list[Profile],
    bucket_seconds: int,
    pause_threshold: float,
    match_threshold: float = CONFIDENCE_MATCH_THRESHOLD,
    dtw_window: int | None = 3,
) -> tuple[Profile, bool]:
    """Assign a finished run to an existing profile, or create a new one.

    Args:
        run: The finished run to classify.
        profiles: Currently known profiles for this device.
        bucket_seconds: Band bucket width in seconds, matching ``profiles``.
        pause_threshold: Power (W) below which a bucket counts as a pause,
            used only when a new profile has to be created.
        match_threshold: Minimum DTW confidence (%) to count as a match.
        dtw_window: Sakoe-Chiba window passed to the DTW alignment.

    Returns:
        A tuple ``(profile, is_new)``: the matched (band-widened) existing
        profile with ``is_new=False``, or a freshly created profile with
        ``is_new=True``. Callers are responsible for persisting the result
        (replacing the matched profile, or appending the new one).
    """
    run_values = [b.mean for b in build_band(list(run.samples), bucket_seconds, end=_run_end(run))]

    best_profile: Profile | None = None
    best_confidence = -1.0
    for profile in profiles:
        band_slice = profile.buckets[: len(run_values) + _MATCH_LOOKAHEAD_BUCKETS]
        if not band_slice:
            continue
        cost = band_aware_dtw_cost(run_values, band_slice, window=dtw_window)
        confidence = confidence_percent(cost, run_values, band_slice)
        if confidence > best_confidence:
            best_confidence = confidence
            best_profile = profile

    if best_profile is not None and best_confidence >= match_threshold:
        return merge_run_into_profile(best_profile, run, bucket_seconds), False

    return create_profile_from_run(run, bucket_seconds, pause_threshold), True


def detect_profiles(
    runs: list[DeviceRun],
    bucket_seconds: int,
    pause_threshold: float,
    match_threshold: float = CONFIDENCE_MATCH_THRESHOLD,
    dtw_window: int | None = 3,
) -> list[Profile]:
    """Discover profiles from a batch of historical runs (automatic analysis).

    Runs are folded in chronologically, each either widening a matching
    profile's band or starting a new one, per Specs.md "Analyse von
    Lastprofilen" (automatischer Modus über die kompletten 30 Tage).

    Args:
        runs: Finished runs to analyze, ideally in chronological order.
        bucket_seconds: Band bucket width in seconds (Richtwert 5-10s).
        pause_threshold: Power (W) below which a bucket counts as a pause.
        match_threshold: Minimum DTW confidence (%) to count as a match.
        dtw_window: Sakoe-Chiba window passed to the DTW alignment.

    Returns:
        The resulting list of profiles.
    """
    profiles: list[Profile] = []
    for run in runs:
        profile, is_new = assign_run(
            run, profiles, bucket_seconds, pause_threshold, match_threshold, dtw_window
        )
        if is_new:
            profiles.append(profile)
        else:
            profiles = [profile if p.id == profile.id else p for p in profiles]
    return profiles


@dataclass(frozen=True, slots=True)
class LiveMatch:
    """Result of matching an in-progress run against known profiles.

    Attributes:
        profile: The profile currently used for the forecast, or ``None``
            if there are no known profiles at all.
        confidence_percent: DTW-based match confidence (0-100) for the
            live run against ``profile`` (or the best-matching profile, if
            ``is_known`` is ``False``).
        is_known: Whether ``confidence_percent`` reaches the match
            threshold. When ``False``, ``profile`` is still populated with
            the worst-case (highest-energy) fallback, per Specs.md.
    """

    profile: Profile | None
    confidence_percent: float
    is_known: bool


def match_live(
    live_samples: list[RawSample],
    profiles: list[Profile],
    bucket_seconds: int,
    match_threshold: float = CONFIDENCE_MATCH_THRESHOLD,
    dtw_window: int | None = 3,
) -> LiveMatch:
    """Match an in-progress run against known profiles for live forecasting.

    Per Specs.md "Erkennen von Lastprofilen während der Nutzung": if several
    profiles currently match, the one with the highest total energy
    ("energetischer Worst Case") is used, so the forecast can only be
    corrected downward as the run continues. If none match, the
    highest-energy profile among *all* known profiles is used as a
    fallback forecast, while ``confidence_percent`` still reports the best
    actual match quality found, so callers can surface the uncertainty.

    Args:
        live_samples: Raw samples of the run so far, in chronological order.
        profiles: Currently known profiles for this device.
        bucket_seconds: Band bucket width in seconds, matching ``profiles``.
        match_threshold: Minimum DTW confidence (%) to count as a match.
        dtw_window: Sakoe-Chiba window passed to the DTW alignment.

    Returns:
        The resulting :class:`LiveMatch`.
    """
    if not profiles or not live_samples:
        return LiveMatch(profile=None, confidence_percent=0.0, is_known=False)

    live_end = live_samples[-1].timestamp
    live_values = [b.mean for b in build_band(live_samples, bucket_seconds, end=live_end)]
    if not live_values:
        return LiveMatch(profile=None, confidence_percent=0.0, is_known=False)

    scored: list[tuple[Profile, float]] = []
    for profile in profiles:
        if not profile.buckets:
            continue
        # open_end: a live run is a prefix of the eventual full profile, so
        # the alignment must consume every live reading but may end
        # anywhere along the (possibly much longer) profile band.
        cost = band_aware_dtw_cost(live_values, profile.buckets, window=dtw_window, open_end=True)
        band_slice = profile.buckets[: len(live_values) + _MATCH_LOOKAHEAD_BUCKETS] or profile.buckets
        scored.append((profile, confidence_percent(cost, live_values, band_slice)))

    if not scored:
        return LiveMatch(profile=None, confidence_percent=0.0, is_known=False)

    matching = [(p, c) for p, c in scored if c >= match_threshold]
    if matching:
        best_profile, best_confidence = max(matching, key=lambda item: item[0].total_energy_wh())
        return LiveMatch(profile=best_profile, confidence_percent=best_confidence, is_known=True)

    fallback_profile = max(scored, key=lambda item: item[0].total_energy_wh())[0]
    best_confidence = max(confidence for _, confidence in scored)
    return LiveMatch(profile=fallback_profile, confidence_percent=best_confidence, is_known=False)


def merge_profiles(profiles: list[Profile], name: str) -> Profile:
    """Merge two or more profiles into one, per user request (Dashboard/Pflege).

    Args:
        profiles: The profiles to merge (at least one).
        name: Name for the resulting merged profile, as chosen by the user.

    Returns:
        A new profile whose band covers the union of all input profiles'
        bands, bucket-wise.

    Raises:
        ValueError: If ``profiles`` is empty.
    """
    if not profiles:
        raise ValueError("Cannot merge an empty list of profiles")

    bucket_count = max(len(profile.buckets) for profile in profiles)
    merged_buckets: list[BandBucket] = []
    for index in range(bucket_count):
        contributing = [p.buckets[index] for p in profiles if index < len(p.buckets)]
        merged_buckets.append(
            BandBucket(
                offset_seconds=contributing[0].offset_seconds,
                min=min(b.min for b in contributing),
                mean=sum(b.mean for b in contributing) / len(contributing),
                max=max(b.max for b in contributing),
            )
        )

    now = datetime.now(timezone.utc)
    merged_pause_windows = tuple(
        dict.fromkeys(window for profile in profiles for window in profile.pause_windows)
    )
    return Profile(
        id=str(uuid4()),
        name=name,
        buckets=tuple(merged_buckets),
        pause_windows=merged_pause_windows,
        created_at=min(profile.created_at for profile in profiles),
        updated_at=now,
    )
