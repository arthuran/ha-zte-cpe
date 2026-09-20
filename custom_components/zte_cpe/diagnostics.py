"""Diagnostics for ZTE CPE Monitor."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {
    "password",
    "cell_id",
    "lte_pci",
    "nr5g_pci",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Return privacy-conscious diagnostics."""
    coordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }
