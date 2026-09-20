"""ZTE CPE Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import ZTECPEClient
from .const import CONF_URL, PLATFORMS
from .coordinator import ZTECPECoordinator


ZTECPEConfigEntry = ConfigEntry[ZTECPECoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ZTECPEConfigEntry) -> bool:
    """Set up ZTE CPE Monitor from a config entry."""
    client = ZTECPEClient(entry.data[CONF_URL], entry.data["password"])
    coordinator = ZTECPECoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZTECPEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
