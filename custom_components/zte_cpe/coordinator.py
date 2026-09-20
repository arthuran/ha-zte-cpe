"""Data coordinator for ZTE CPE Monitor."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ZTECPEClient, ZTECPEClientError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


class ZTECPECoordinator(DataUpdateCoordinator[dict]):
    """Coordinate polling so all entities share one CPE request cycle."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: ZTECPEClient) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(self.client.snapshot)
        except ZTECPEClientError as exc:
            raise UpdateFailed(str(exc)) from exc
