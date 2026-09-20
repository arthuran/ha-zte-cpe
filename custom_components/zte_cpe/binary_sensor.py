"""Binary sensor platform for ZTE CPE Monitor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZTECPECoordinator


BINARY_SENSORS = (
    BinarySensorEntityDescription(key="wan_connected", name="WAN Connected"),
    BinarySensorEntityDescription(key="ppp_connected", name="PPP Connected"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: ZTECPECoordinator = entry.runtime_data
    async_add_entities(ZTECPEBinarySensor(coordinator, entry, description) for description in BINARY_SENSORS)


class ZTECPEBinarySensor(CoordinatorEntity[ZTECPECoordinator], BinarySensorEntity):
    def __init__(self, coordinator: ZTECPECoordinator, entry: ConfigEntry, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        telemetry = self.coordinator.data.get("telemetry", {})
        if self.entity_description.key == "wan_connected":
            return telemetry.get("wan_connect_status") == "pdp_connected"
        return telemetry.get("ppp_status") == "ppp_connected"

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
