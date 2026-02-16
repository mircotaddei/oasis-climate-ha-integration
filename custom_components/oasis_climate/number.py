"""Support for OASIS Climate numbers."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity # type: ignore
from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore

from .const import DOMAIN
from .coordinator import OasisUpdateCoordinator
from .telemetry_manager import TelemetryManager
from .helpers import async_update_telemetry_config


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OASIS numbers."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OasisUpdateCoordinator = data["coordinator"]
    telemetry_manager: TelemetryManager = data["telemetry_manager"]
    
    entities = []

    # Global Telemetry Numbers
    entities.extend([
        OasisBatchSizeNumber(telemetry_manager, entry),
        OasisFlushIntervalNumber(telemetry_manager, entry)
    ])

    # Specific Numbers for Sensors (Weight)
    thermostats = coordinator.data.get("thermostats", {})
    for t_device_id, t_data in thermostats.items():
        sensors_map = t_data.get("sensors_map", {})
        for s_device_id, s_data in sensors_map.items():
            entities.append(OasisSensorWeightNumber(coordinator, t_device_id, s_device_id))
            entities.append(OasisHumidityNumber(coordinator, t_device_id))

    async_add_entities(entities)


# --- BATCH SIZE NUMBER -------------------------------------------------------

class OasisBatchSizeNumber(NumberEntity):
    """Control the telemetry batch size."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "telemetry_batch_size"
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_icon = "mdi:package-variant-closed"

    def __init__(self, telemetry_manager: TelemetryManager, entry: ConfigEntry) -> None:
        self._manager = telemetry_manager
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_batch_size"

    @property
    def native_value(self) -> float:
        return float(self._manager._batch_size)


    # --- SET NATIVE VALUE -----------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        await async_update_telemetry_config(self.hass, self._entry, self._manager, "telemetry_batch_size", int(value))
        self.async_write_ha_state()


# --- OASIS FLUSH INTERVAL NUMBER ---------------------------------------------

class OasisFlushIntervalNumber(NumberEntity):
    """Control the telemetry flush interval."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "telemetry_flush_interval"
    _attr_native_min_value = 60
    _attr_native_max_value = 900
    _attr_native_step = 60
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer-sand"

    def __init__(self, telemetry_manager: TelemetryManager, entry: ConfigEntry) -> None:
        self._manager = telemetry_manager
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_flush_interval"

    @property
    def native_value(self) -> float:
        return float(self._manager._flush_interval)


    # --- SET NATIVE VALUE -----------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        await async_update_telemetry_config(self.hass, self._entry, self._manager, "telemetry_flush_interval", int(value))
        self.async_write_ha_state()


# --- OASIS SENSOR WEIGHT NUMBER ----------------------------------------------

class OasisSensorWeightNumber(CoordinatorEntity, NumberEntity):
    """Number to adjust the weight of a Sensor."""
    
    _attr_has_entity_name = True
    _attr_name = "Weight"
    _attr_icon = "mdi:weight"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 1.0
    _attr_native_step = 0.1

    def __init__(self, coordinator: OasisUpdateCoordinator, thermostat_id: str, sensor_id: str):
        super().__init__(coordinator)
        self._t_id = thermostat_id
        self._s_id = sensor_id
        self._attr_unique_id = f"oasis_sensor_weight_{sensor_id}"
        
        # Connect this entity to the thermostat device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{thermostat_id}")}
        )

    @property
    def native_value(self) -> float | None:
        try:
            s_data = self.coordinator.data["thermostats"][self._t_id]["sensors_map"][self._s_id]
            return s_data.get("weight", 1.0)
        except KeyError:
            return None


    # --- SET NATIVE VALUE -----------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.sensors.update(self._s_id, {"weight": value})
        await self.coordinator.async_request_refresh()


# --- OASIS HUMIDITY NUMBER ---------------------------------------------------

class OasisHumidityNumber(CoordinatorEntity, NumberEntity):
    """Target Humidity for the thermostat."""
    _attr_has_entity_name = True
    _attr_name = "Target Humidity"
    _attr_icon = "mdi:water-percent"
    _attr_native_min_value = 30
    _attr_native_max_value = 80
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: OasisUpdateCoordinator, device_id: str):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_humidity_{device_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data["thermostats"].get(self._device_id, {})
        return data.get("humidity_setpoint")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.thermostats.update_state(self._device_id, {"humidity_setpoint": value})
        await self.coordinator.async_request_refresh()