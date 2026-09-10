"""Detect device runs (program start/end) from a stream of raw power samples.

Per Specs.md "Analyse von Lastprofilen": a run starts when power exceeds a
threshold and ends only once power has stayed below that threshold for a
continuous duration (``end_timeout_seconds``). That timeout is deliberately
a parameter here, not a fixed constant - callers derive it from the longest
known pause of the candidate profiles (see :mod:`..analysis.clustering`),
so that a profile-internal pause is never mistaken for the run's end.
"""

from __future__ import annotations

from ..models import DeviceRun, RawSample


def detect_runs(
    samples: list[RawSample], start_threshold: float, end_timeout_seconds: float
) -> list[DeviceRun]:
    """Split a chronological sample stream into individual device runs.

    Args:
        samples: Raw samples in chronological order.
        start_threshold: Power (W) above which a run is considered started.
        end_timeout_seconds: How long power must stay at or below
            ``start_threshold`` before a run is considered ended. A dip
            shorter than this is treated as an in-program pause, not an end.

    Returns:
        Detected runs in chronological order. A run still in progress at
        the end of ``samples`` is included with ``ended_at=None``.

    Note:
        Home Assistant's recorder does not re-log an unchanged state, so a
        device sitting idle for a long time typically produces exactly one
        below-threshold sample, then nothing until the next real run
        starts. The timeout is therefore checked against every incoming
        sample's timestamp - including one that itself jumps back above
        the threshold - not only against a later below-threshold sample;
        otherwise a run could never close without an intervening
        below-threshold reading, silently merging separate real runs
        (potentially days apart) into one.
    """
    runs: list[DeviceRun] = []
    started_at = None
    run_samples: list[RawSample] = []
    below_since = None

    for sample in samples:
        if started_at is not None and below_since is not None:
            elapsed = (sample.timestamp - below_since).total_seconds()
            if elapsed >= end_timeout_seconds:
                runs.append(
                    DeviceRun(
                        started_at=started_at,
                        ended_at=below_since,
                        samples=tuple(s for s in run_samples if s.timestamp <= below_since),
                    )
                )
                started_at = None
                run_samples = []
                below_since = None

        if started_at is None:
            if sample.value > start_threshold:
                started_at = sample.timestamp
                run_samples = [sample]
                below_since = None
            continue

        run_samples.append(sample)
        if sample.value <= start_threshold:
            if below_since is None:
                below_since = sample.timestamp
        else:
            below_since = None

    if started_at is not None:
        runs.append(DeviceRun(started_at=started_at, ended_at=None, samples=tuple(run_samples)))

    return runs
