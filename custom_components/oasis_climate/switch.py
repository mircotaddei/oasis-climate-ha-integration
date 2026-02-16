"""Support for OASIS Climate switches."""
from __future__ import annotations
from typing import Any

from homeassistant.components.switch import SwitchEntity # type: ignore
from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore

from .const import DOMAIN, CONF_HOME_ID
from .coordinator import OasisUpdateCoordinator
from .telemetry_manager import TelemetryManager
from .helpers import async_update_telemetry_config


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OASIS switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OasisUpdateCoordinator = data["coordinator"]
    telemetry_manager: TelemetryManager = data["telemetry_manager"]
    
    entities = []

    # Home Switches
    home_id = str(entry.data[CONF_HOME_ID])
    entities.append(OasisHomeHolidaySwitch(coordinator, home_id))

    # Global Telemetry Switch
    entities.append(OasisTelemetrySwitch(telemetry_manager, entry))

    # Specific Switches for Devices (Thermostats and Sensors)
    thermostats = coordinator.data.get("thermostats", {})
    
    for t_device_id, t_data in thermostats.items():
        # Switch Thermostat Configuration
        entities.append(OasisThermostatSafetySwitch(coordinator, t_device_id))
        
        # Switch Sensor Configuration
        sensors_map = t_data.get("sensors_map", {})
        for s_device_id, s_data in sensors_map.items():
            entities.append(OasisSensorActiveSwitch(coordinator, t_device_id, s_device_id))
            

    async_add_entities(entities)


# --- OASIS TELEMETRY SWITCH -------------------------------------------------

class OasisTelemetrySwitch(SwitchEntity):
    """Global switch to enable/disable telemetry."""

    _attr_has_entity_name = True
    _attr_translation_key = "telemetry_enabled"
    _attr_icon = "mdi:server-network"

    def __init__(self, telemetry_manager: TelemetryManager, entry: ConfigEntry) -> None:
        self._manager = telemetry_manager
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_telemetry_enable"

    @property
    def is_on(self) -> bool:
        return self._manager._enabled


    # --- TURN ON --------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_update_telemetry_config(self.hass, self._entry, self._manager, "telemetry_enabled", True)
        self.async_write_ha_state()


    # --- TURN OFF -------------------------------------------------------------

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_update_telemetry_config(self.hass, self._entry, self._manager, "telemetry_enabled", False)
        self.async_write_ha_state()


# --- THERMOSTAT SAFETY SWITCH ------------------------------------------------

class OasisThermostatSafetySwitch(CoordinatorEntity, SwitchEntity):
    """Switch to toggle Force Safety Mode on a Thermostat."""
    
    _attr_has_entity_name = True
    _attr_name = "Force Safety Mode"
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator: OasisUpdateCoordinator, device_id: str):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_thermostat_safety_{device_id}"
        # Connect this switch to the thermostat device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{device_id}")}
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data.get("thermostats", {}).get(self._device_id, {})
        return data.get("force_safety_mode", False)


    # --- TURN ON --------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.thermostats.update_config(self._device_id, {"force_safety_mode": True})
        await self.coordinator.async_request_refresh()


    # --- TURN OFF -------------------------------------------------------------

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.thermostats.update_config(self._device_id, {"force_safety_mode": False})
        await self.coordinator.async_request_refresh()



# --- OASIS SENSOR ACTIVE SWITCH ----------------------------------------------

class OasisSensorActiveSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to toggle Active status of a Sensor."""
    
    _attr_has_entity_name = True
    _attr_name = "Active" # Will appear as "Sensor Name Active" if grouped, or under the device
    _attr_icon = "mdi:eye"

    def __init__(self, coordinator: OasisUpdateCoordinator, thermostat_id: str, sensor_id: str):
        super().__init__(coordinator)
        self._t_id = thermostat_id
        self._s_id = sensor_id
        self._attr_unique_id = f"oasis_sensor_active_{sensor_id}"
        
        # Connect this switch to the thermostat device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{thermostat_id}")}
        )

    @property
    def is_on(self) -> bool | None:
        try:
            s_data = self.coordinator.data["thermostats"][self._t_id]["sensors_map"][self._s_id]
            return s_data.get("is_active", True)
        except KeyError:
            return None


    # --- TURN ON --------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.sensors.update(self._s_id, {"is_active": True})
        await self.coordinator.async_request_refresh()


    # --- TURN OFF -------------------------------------------------------------

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.sensors.update(self._s_id, {"is_active": False})
        await self.coordinator.async_request_refresh()


# --- OASIS HOME HOLIDAY SWITCH -----------------------------------------------

class OasisHomeHolidaySwitch(CoordinatorEntity, SwitchEntity):
    """Global Holiday Mode for the Home."""
    _attr_has_entity_name = True
    _attr_name = "Holiday Mode"
    _attr_icon = "mdi:bag-suitcase"

    def __init__(self, coordinator, home_id):
        super().__init__(coordinator)
        self._home_id = home_id
        self._attr_unique_id = f"oasis_home_holiday_{home_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"home_{home_id}")})

    @property
    def is_on(self) -> bool | None:
        # Assumiamo che 'away' sia la modalità vacanza
        return self.coordinator.data.get("home", {}).get("hvac_mode") == "away"

    async def async_turn_on(self, **kwargs):
        # TODO must create a method in HomeApi to set Holiday Mode
        # await self.coordinator.client.homes.update(self._home_id, {"hvac_mode": "away"})
        pass 

    async def async_turn_off(self, **kwargs):
        # TODO must create a method in HomeApi to set Auto Mode
        # await self.coordinator.client.homes.update(self._home_id, {"hvac_mode": "auto"})
        pass