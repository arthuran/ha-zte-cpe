"""Field-level last-known-value retention for partial CPE responses."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

FIELD_STALE_GRACE = 3
STATE_SECTIONS = ("radio", "telemetry")


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def merge_snapshot_fields(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    miss_counts: dict[str, int],
    *,
    grace: int = FIELD_STALE_GRACE,
) -> tuple[dict[str, Any], dict[str, int], set[str]]:
    """Merge partial current data with recent good field values.

    Empty/missing values are treated as transient for up to ``grace`` successful
    polling cycles.  After that, the empty value is allowed through so a radio
    technology that is genuinely no longer active does not display stale data
    forever.
    """
    merged = deepcopy(current)
    updated_counts: dict[str, int] = {}
    stale_fields: set[str] = set()

    if previous is None:
        return merged, updated_counts, stale_fields

    for section in STATE_SECTIONS:
        previous_section = previous.get(section, {})
        current_section = current.get(section, {})
        merged_section = merged.setdefault(section, {})

        for field in set(previous_section) | set(current_section):
            path = f"{section}.{field}"
            new_value = current_section.get(field)
            old_value = previous_section.get(field)

            if _has_value(new_value):
                merged_section[field] = new_value
                continue

            if not _has_value(old_value):
                merged_section[field] = new_value if field in current_section else ""
                continue

            misses = miss_counts.get(path, 0) + 1
            if misses <= grace:
                merged_section[field] = old_value
                updated_counts[path] = misses
                stale_fields.add(path)
            else:
                merged_section[field] = new_value if field in current_section else ""

    return merged, updated_counts, stale_fields
