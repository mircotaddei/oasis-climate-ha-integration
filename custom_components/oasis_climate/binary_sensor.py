"""Support for OASIS Climate binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import ( # type: ignore
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore

from .const import DOMAIN
from .coordinator import OasisUpdateCoordinator


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OASIS binary sensors."""
    coordinator: OasisUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []

    for t_device_id in coordinator.data.get("thermostats", {}):
        entities.append(OasisConnectivitySensor(coordinator, t_device_id))

    async_add_entities(entities)


# --- OASIS CONNECTIVITY SENSOR -----------------------------------------------

class OasisConnectivitySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of the thermostat connectivity status."""

    _attr_has_entity_name = True
    _attr_name = "Connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: OasisUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_connectivity_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{device_id}")}
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is connected."""
        data = self.coordinator.data.get("thermostats", {}).get(self._device_id, {})
        return data.get("is_online", False)