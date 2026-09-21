"""Sensor platform for ZTE CPE Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZTECPECoordinator


@dataclass(frozen=True, kw_only=True)
class ZTECPESensorDescription(SensorEntityDescription):
    """Describe a ZTE CPE sensor."""

    section: str
    field: str
    value_fn: Callable[[Any], Any] | None = None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


SENSORS: tuple[ZTECPESensorDescription, ...] = (
    ZTECPESensorDescription(key="lte_rsrp", name="LTE RSRP", section="radio", field="lte_rsrp", native_unit_of_measurement="dBm", value_fn=_float),
    ZTECPESensorDescription(key="lte_rsrq", name="LTE RSRQ", section="radio", field="lte_rsrq", native_unit_of_measurement="dB", value_fn=_float),
    ZTECPESensorDescription(key="lte_sinr", name="LTE SINR", section="radio", field="lte_snr", native_unit_of_measurement="dB", value_fn=_float),
    ZTECPESensorDescription(key="lte_band", name="LTE Band", section="radio", field="wan_active_band"),
    ZTECPESensorDescription(key="nr5g_rsrp", name="5G RSRP", section="radio", field="Z5g_rsrp", native_unit_of_measurement="dBm", value_fn=_float),
    ZTECPESensorDescription(key="nr5g_sinr", name="5G SINR", section="radio", field="Z5g_SINR", native_unit_of_measurement="dB", value_fn=_float),
    ZTECPESensorDescription(key="nr5g_band", name="5G Band", section="radio", field="nr5g_action_band"),
    ZTECPESensorDescription(key="signal_bars", name="Signal Bars", section="radio", field="signalbar", value_fn=_int),
    ZTECPESensorDescription(key="session_uptime", name="Session Uptime", section="telemetry", field="realtime_time", native_unit_of_measurement="s", value_fn=_int),
    ZTECPESensorDescription(key="realtime_tx", name="Realtime TX", section="telemetry", field="realtime_tx_bytes", native_unit_of_measurement=UnitOfInformation.BYTES, value_fn=_int),
    ZTECPESensorDescription(key="realtime_rx", name="Realtime RX", section="telemetry", field="realtime_rx_bytes", native_unit_of_measurement=UnitOfInformation.BYTES, value_fn=_int),
    ZTECPESensorDescription(key="tx_rate", name="TX Rate", section="telemetry", field="realtime_tx_thrpt", native_unit_of_measurement="B/s", value_fn=_int),
    ZTECPESensorDescription(key="rx_rate", name="RX Rate", section="telemetry", field="realtime_rx_thrpt", native_unit_of_measurement="B/s", value_fn=_int),
    ZTECPESensorDescription(key="monthly_tx", name="Monthly TX", section="telemetry", field="monthly_tx_bytes", native_unit_of_measurement=UnitOfInformation.BYTES, value_fn=_int),
    ZTECPESensorDescription(key="monthly_rx", name="Monthly RX", section="telemetry", field="monthly_rx_bytes", native_unit_of_measurement=UnitOfInformation.BYTES, value_fn=_int),
    ZTECPESensorDescription(key="monthly_time", name="Monthly Connected Time", section="telemetry", field="monthly_time", native_unit_of_measurement="s", value_fn=_int),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZTE CPE sensors."""
    coordinator: ZTECPECoordinator = entry.runtime_data
    async_add_entities(ZTECPESensor(coordinator, entry, description) for description in SENSORS)


class ZTECPESensor(CoordinatorEntity[ZTECPECoordinator], SensorEntity):
    """Representation of a ZTE CPE sensor."""

    entity_description: ZTECPESensorDescription

    def __init__(self, coordinator: ZTECPECoordinator, entry: ConfigEntry, description: ZTECPESensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._entry = entry

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.entity_description.section, {}).get(self.entity_description.field)
        if value in (None, ""):
            return None
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(value)
        return value

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        path = f"{self.entity_description.section}.{self.entity_description.field}"
        stale_fields = self.coordinator.data.get("health", {}).get("stale_fields", [])
        return {"data_stale": path in stale_fields}

    @property
    def device_info(self) -> DeviceInfo:
        device = self.coordinator.data.get("device", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=device.get("model") or "ZTE CPE",
            manufacturer="ZTE",
            model=device.get("model") or None,
            hw_version=device.get("hardware_version") or None,
            sw_version=device.get("firmware_version") or None,
            configuration_url=self._entry.data.get("url"),
        )
