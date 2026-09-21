"""Data coordinator for ZTE CPE Monitor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ZTECPEClient, ZTECPEClientError
from .const import DOMAIN
from .field_state import merge_snapshot_fields
from .polling import (
    NORMAL_INTERVAL,
    TRANSIENT_FAILURE_GRACE,
    failure_backoff_seconds,
    next_success_interval,
)

_LOGGER = logging.getLogger(__name__)


class ZTECPECoordinator(DataUpdateCoordinator[dict]):
    """Coordinate polling so all entities share one CPE request cycle."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: ZTECPEClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=NORMAL_INTERVAL),
            always_update=False,
        )
        self.client = client
        self._last_good_snapshot: dict | None = None
        self._field_miss_counts: dict[str, int] = {}
        self._stale_fields: set[str] = set()
        self._stable_polls = 0
        self._failure_count = 0
        self._last_success_at: str | None = None
        self.poll_interval_seconds = NORMAL_INTERVAL

    def _with_health(self, data: dict, *, stale: bool) -> dict:
        result = dict(data)
        stale_fields = sorted(self._stale_fields)
        result["health"] = {
            "stale": stale or bool(stale_fields),
            "partial_stale": bool(stale_fields),
            "stale_fields": stale_fields,
            "stale_field_count": len(stale_fields),
            "consecutive_failures": self._failure_count,
            "poll_interval_seconds": self.poll_interval_seconds,
            "last_success_at": self._last_success_at,
            "reauth_count": self.client.reauth_count,
            "session_age_seconds": self.client._session_age_seconds(),
        }
        return result

    def _record_success(self, data: dict) -> dict:
        merged, miss_counts, stale_fields = merge_snapshot_fields(
            self._last_good_snapshot,
            data,
            self._field_miss_counts,
        )
        interval, stable_polls = next_success_interval(
            self._last_good_snapshot,
            merged,
            self._stable_polls,
            self.poll_interval_seconds,
        )
        self._field_miss_counts = miss_counts
        self._stale_fields = stale_fields
        self._stable_polls = stable_polls
        self._failure_count = 0
        self._last_good_snapshot = merged
        self._last_success_at = datetime.now(timezone.utc).isoformat()
        self.poll_interval_seconds = interval
        self.update_interval = timedelta(seconds=interval)
        return self._with_health(merged, stale=False)

    async def _async_update_data(self) -> dict:
        try:
            data = await self.hass.async_add_executor_job(self.client.snapshot)
        except ZTECPEClientError as exc:
            self._failure_count += 1
            retry_after = failure_backoff_seconds(self._failure_count)
            self.poll_interval_seconds = retry_after
            self.update_interval = timedelta(seconds=retry_after)

            if (
                self._last_good_snapshot is not None
                and self._failure_count <= TRANSIENT_FAILURE_GRACE
            ):
                _LOGGER.warning(
                    "ZTE CPE poll failed (%s/%s); keeping last-known data and retrying in %ss",
                    self._failure_count,
                    TRANSIENT_FAILURE_GRACE,
                    retry_after,
                )
                return self._with_health(self._last_good_snapshot, stale=True)

            raise UpdateFailed(str(exc), retry_after=retry_after) from exc

        return self._record_success(data)
