"""Support for OASIS Climate thermostats."""
from __future__ import annotations
import logging

from typing import Any

from homeassistant.components.climate import (ClimateEntity, ClimateEntityFeature, HVACMode, ) # type: ignore
from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore

from .const import DOMAIN
from .coordinator import OasisUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OASIS Climate entities."""
    coordinator: OasisUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities = []
    # Itera sui termostati presenti nel coordinator
    for t_id in coordinator.data.get("thermostats", {}):
        entities.append(OasisThermostat(coordinator, int(t_id)))
    
    async_add_entities(entities)


# --- OASIS THERMOSTAT --------------------------------------------------------

class OasisThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of an OASIS Thermostat."""

    # --- ATTRIBUTI STATICI OBBLIGATORI ---
    _attr_has_entity_name = True
    _attr_name = None  # Usa il nome del dispositivo
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator: OasisUpdateCoordinator, thermostat_id: int) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._id = thermostat_id
        self._attr_unique_id = f"oasis_thermostat_{self._id}"
        
        # Link al Device creato in __init__.py
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{self._id}")},
        )

    @property
    def _thermostat_data(self) -> dict[str, Any]:
        """Get the latest data for this specific thermostat."""
        return self.coordinator.data.get("thermostats", {}).get(self._id, {})

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._thermostat_data.get("current_temp_in")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._thermostat_data.get("heat_setpoint")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        mode = self._thermostat_data.get("hvac_mode", "off")
        if mode == "heat":
            return HVACMode.HEAT
        elif mode == "cool":
            return HVACMode.COOL
        elif mode == "auto":
            return HVACMode.AUTO
        return HVACMode.OFF


    # --- SET HVAC MODE --------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # Map HA mode to backend mode string
        mode_map = {
            HVACMode.HEAT: "heat",
            HVACMode.COOL: "cool",
            HVACMode.AUTO: "auto",
            HVACMode.OFF: "off",
        }
        api_mode = mode_map.get(hvac_mode, "off")

        _LOGGER.debug("Setting HVAC mode for %s to %s", self.unique_id, api_mode)
        success = await self.coordinator.client.thermostats.update_state(
            self._id, {"hvac_mode": api_mode}
        )
        
        if success:
            # Request a refresh to immediately reflect the change in HA state
            await self.coordinator.async_request_refresh()


    # --- SET TEMPERATURE ------------------------------------------------------
    
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting target temperature for %s to %s", self.unique_id, temp)
            
            # Assuming heat_setpoint for simplicity. A real implementation
            # might need to check the current HVAC mode.
            success = await self.coordinator.client.thermostats.update_state(
                self._id, {"heat_setpoint": temp}
            )
            
            if success:
                await self.coordinator.async_request_refresh()

    # async def async_will_remove_from_hass(self) -> None:
    #     """
    #     Handle entity removal from Home Assistant.
    #     This is triggered when a device is deleted from the UI.
    #     """
    #     _LOGGER.warning(
    #         "Thermostat %s is being removed from HA. Deleting from backend.", self._id
    #     )
    #     await self.coordinator.client.thermostats.delete(self._id)