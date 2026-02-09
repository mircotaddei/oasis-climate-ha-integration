"""Support for OASIS Climate sensors."""
from __future__ import annotations
import logging

from homeassistant.components.sensor import (SensorEntity, SensorDeviceClass, SensorStateClass, ) # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.const import UnitOfTemperature, PERCENTAGE # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore

from .const import DOMAIN, SENSOR_TYPES_REV
from .coordinator import OasisUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# Mappa per configurare le unità e le classi in base al tipo
SENSOR_CONFIG = {
    "temp_in": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "label": "Temperature (Indoor)"
    },
    "temp_out": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "label": "Temperature (Outdoor)"
    },
    "humidity_in": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "icon": "mdi:water-percent",
        "label": "Humidity (Indoor)"
    },
    "humidity_out": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "icon": "mdi:water-percent",
        "label": "Humidity (Outdoor)"
    },
    "luminosity": {
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "unit": "lx",
        "icon": "mdi:brightness-5",
        "label": "Luminosity"
    },
    # Default fallback
    "default": {
        "device_class": None,
        "unit": None,
        "icon": "mdi:eye",
        "label": "Sensor"
    }
}


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OASIS sensors."""
    coordinator: OasisUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities = []
    thermostats = coordinator.data.get("thermostats", {})
    
    _LOGGER.debug("Setting up sensors. Found %d thermostats.", len(thermostats))

    for t_id, t_data in thermostats.items():
        sensors_map = t_data.get("sensors_map", {})
        _LOGGER.debug("Thermostat %s has %d sensors mapped.", t_id, len(sensors_map))
        
        for s_id, s_data in sensors_map.items():
            _LOGGER.debug("Creating sensor entity for: %s (Type: %s)", s_data.get("name"), s_data.get("type"))
            entities.append(OasisSensor(coordinator, t_id, int(s_id)))
            
    async_add_entities(entities)


# --- OASIS SENSOR ------------------------------------------------------------

class OasisSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OASIS Sensor linked to a Thermostat."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: OasisUpdateCoordinator, thermostat_id: int, sensor_id: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thermostat_id = thermostat_id
        self._sensor_id = sensor_id
        
        # Unique ID for the entity
        self._attr_unique_id = f"oasis_sensor_{self._sensor_id}"
        
        # Link this entity to the parent Thermostat Device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{self._thermostat_id}")},
        )
        
        # Set initial static attributes
        self._update_static_attributes()

    @property
    def _sensor_data(self) -> dict | None:
        """Helper to get the data for this specific sensor from the coordinator."""
        try:
            return self.coordinator.data["thermostats"][self._thermostat_id]["sensors_map"][self._sensor_id]
        except KeyError:
            return None

    def _update_static_attributes(self) -> None:
        """Update static attributes based on the sensor's type."""
        if not self._sensor_data:
            return

        sensor_type = self._sensor_data.get("type")
        config = SENSOR_CONFIG.get(sensor_type, {}) # type: ignore
        
        # The entity name will be the friendly name from the backend
        self._attr_name = self._sensor_data.get("name") or SENSOR_TYPES_REV.get(sensor_type, "Sensor") # type: ignore
        
        self._attr_device_class = config.get("device_class")
        self._attr_native_unit_of_measurement = config.get("unit")

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        if self._sensor_data:
            # The backend provides the last known value in 'cached_value'
            return self._sensor_data.get("cached_value")
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # The entity is available if its data exists in the coordinator
        # and the coordinator is successfully updating.
        return self._sensor_data is not None and super().available

    # async def async_will_remove_from_hass(self) -> None:
    #     """Handle entity removal from Home Assistant."""
    #     # Note: Deleting a sensor mapping is not typically done by deleting the entity.
    #     # It should be handled via an Options Flow. This is a safeguard.
    #     _LOGGER.warning(
    #         "Sensor %s is being removed from HA. Deleting mapping from backend.", self._sensor_id
    #     )
    #     await self.coordinator.client.sensors.delete(self._sensor_id)