"""Adaptive polling policy for ZTE CPE Monitor."""

from __future__ import annotations

from typing import Any

FAST_INTERVAL = 30
NORMAL_INTERVAL = 60
SLOW_INTERVAL = 120
MAX_BACKOFF_INTERVAL = 900
STABLE_POLLS_AFTER_CHANGE = 3
STABLE_POLLS_TO_SLOW = 8
TRANSIENT_FAILURE_GRACE = 2

_DISCRETE_RADIO_FIELDS = (
    "network_type",
    "signalbar",
    "wan_active_band",
    "wan_active_channel",
    "nr5g_action_band",
    "nr5g_action_channel",
    "wan_lte_ca",
    "lte_multi_ca_scell_info",
)

_DISCRETE_TELEMETRY_FIELDS = (
    "wan_connect_status",
    "ppp_status",
)

_SIGNAL_THRESHOLDS = {
    "lte_rsrp": 3.0,
    "lte_rsrq": 2.0,
    "lte_snr": 3.0,
    "Z5g_rsrp": 3.0,
    "Z5g_SINR": 3.0,
}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def has_meaningful_change(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    """Return True when radio/connection state changed enough to justify fast polling."""
    previous_radio = previous.get("radio", {})
    current_radio = current.get("radio", {})
    previous_telemetry = previous.get("telemetry", {})
    current_telemetry = current.get("telemetry", {})

    for field in _DISCRETE_RADIO_FIELDS:
        old = previous_radio.get(field)
        new = current_radio.get(field)
        if old not in (None, "") and new not in (None, "") and old != new:
            return True

    for field in _DISCRETE_TELEMETRY_FIELDS:
        old = previous_telemetry.get(field)
        new = current_telemetry.get(field)
        if old not in (None, "") and new not in (None, "") and old != new:
            return True

    for field, threshold in _SIGNAL_THRESHOLDS.items():
        old = _number(previous_radio.get(field))
        new = _number(current_radio.get(field))
        if old is not None and new is not None and abs(new - old) >= threshold:
            return True

    return False


def next_success_interval(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    stable_polls: int,
    current_interval: int,
) -> tuple[int, int]:
    """Return (next interval seconds, updated stable-poll count)."""
    if previous is None:
        return NORMAL_INTERVAL, 0

    if has_meaningful_change(previous, current):
        return FAST_INTERVAL, 0

    stable_polls += 1
    if current_interval == FAST_INTERVAL and stable_polls < STABLE_POLLS_AFTER_CHANGE:
        return FAST_INTERVAL, stable_polls
    if stable_polls >= STABLE_POLLS_TO_SLOW:
        return SLOW_INTERVAL, stable_polls
    return NORMAL_INTERVAL, stable_polls


def failure_backoff_seconds(failure_count: int) -> int:
    """Return an exponential retry delay, capped to protect low-resource CPEs."""
    failure_count = max(1, failure_count)
    return min(NORMAL_INTERVAL * (2 ** failure_count), MAX_BACKOFF_INTERVAL)
