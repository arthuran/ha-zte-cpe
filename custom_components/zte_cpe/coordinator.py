"""Data coordinator for ZTE CPE Monitor."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ZTECPEClient, ZTECPEClientError
from .const import DOMAIN
from .polling import (
    NORMAL_INTERVAL,
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
        self._last_snapshot: dict | None = None
        self._stable_polls = 0
        self._failure_count = 0
        self.poll_interval_seconds = NORMAL_INTERVAL

    def _record_success(self, data: dict) -> None:
        interval, stable_polls = next_success_interval(
            self._last_snapshot,
            data,
            self._stable_polls,
            self.poll_interval_seconds,
        )
        self._stable_polls = stable_polls
        self._failure_count = 0
        self._last_snapshot = data
        self.poll_interval_seconds = interval
        self.update_interval = timedelta(seconds=interval)

    async def _async_update_data(self) -> dict:
        try:
            data = await self.hass.async_add_executor_job(self.client.snapshot)
        except ZTECPEClientError as exc:
            self._failure_count += 1
            retry_after = failure_backoff_seconds(self._failure_count)
            raise UpdateFailed(str(exc), retry_after=retry_after) from exc

        self._record_success(data)
        return data
