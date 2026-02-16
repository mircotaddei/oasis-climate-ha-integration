"""Support for OASIS Climate thermostats."""
from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction # type: ignore
from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore
from homeassistant.exceptions import HomeAssistantError # type: ignore

from .const import DOMAIN
from .coordinator import OasisUpdateCoordinator
from .api.base_api import OasisApiError

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
    # Itera sui termostati presenti nel coordinator.
    # CRITICO: La chiave del dizionario 'thermostats' è ora il device_id (stringa).
    for device_id in coordinator.data.get("thermostats", {}):
        entities.append(OasisThermostat(coordinator, str(device_id)))
    
    async_add_entities(entities)


# --- OASIS THERMOSTAT --------------------------------------------------------

class OasisThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of an OASIS Thermostat."""

    _attr_has_entity_name = True
    _attr_name = None  # Usa il nome del dispositivo definito nel Device Registry
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator: OasisUpdateCoordinator, device_id: str) -> None:
        """Initialize the thermostat using device_id (str)."""
        super().__init__(coordinator)
        self._device_id = device_id
        
        # CRITICO: _attr_unique_id è la chiave interna di HA. 
        # Deve essere univoca e stabile. Usiamo il device_id del backend.
        self._attr_unique_id = f"oasis_thermostat_{self._device_id}"
        
        # Link al Device nel registro (deve coincidere con quello creato in __init__.py)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{self._device_id}")},
        )

    @property
    def _thermostat_data(self) -> dict[str, Any]:
        """Get the latest data for this specific thermostat from coordinator."""
        # Recupera i dati usando la chiave stringa
        return self.coordinator.data.get("thermostats", {}).get(self._device_id, {})

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        data = self._thermostat_data
        
        # Se non ci sono dati, significa che il coordinator non ha trovato questo ID
        if not data:
            _LOGGER.warning(
                "Thermostat %s unavailable. Coordinator keys: %s", 
                self._device_id, 
                list(self.coordinator.data.get("thermostats", {}).keys())
            )
            return False

        # Se i dati ci sono, controlliamo il flag is_online del backend
        # Default a True se il campo manca
        # return super().available and data.get("is_online", True)
        return super().available and data.get("is_online", True)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._thermostat_data.get("current_temp_in")

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._thermostat_data.get("current_humidity")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        # In base alla modalità, restituisce il setpoint corretto
        mode = self._thermostat_data.get("hvac_mode")
        if mode == "cool":
            return self._thermostat_data.get("cool_setpoint")
        
        # Default a heat_setpoint per heat, auto e off
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

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        # Recuperiamo le capabilities dal cloud config o dai dati del termostato
        caps = self._thermostat_data.get("capabilities", {})
        
        # OFF e HEAT sono (quasi) sempre disponibili
        modes = [HVACMode.OFF, HVACMode.HEAT]
        
        if caps.get("can_cool", False):
            modes.append(HVACMode.COOL)
        
        # AUTO è disponibile se c'è intelligenza a bordo o cloud
        modes.append(HVACMode.AUTO)
        
        return modes

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        # Calcoliamo l'azione basandoci sulla modulazione
        mode = self.hvac_mode
        modulation = self._thermostat_data.get("current_modulation", 0.0)

        if mode == HVACMode.OFF:
            return HVACAction.OFF
        
        if modulation > 0:
            if mode == HVACMode.COOL:
                return HVACAction.COOLING
            return HVACAction.HEATING
        
        return HVACAction.IDLE


    # --- SET HVAC MODE --------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        mode_map = {
            HVACMode.HEAT: "heat",
            HVACMode.COOL: "cool",
            HVACMode.AUTO: "auto",
            HVACMode.OFF: "off",
        }
        api_mode = mode_map.get(hvac_mode)

        if not api_mode:
            _LOGGER.error("Unsupported HVAC mode: %s", hvac_mode)
            return

        try:
            _LOGGER.debug("Setting HVAC mode for %s to %s", self._device_id, api_mode)
            await self.coordinator.client.thermostats.update_state(
                self._device_id, {"hvac_mode": api_mode}
            )
            # Force refresh to update UI immediately (Optimistic UI)
            await self.coordinator.async_request_refresh()
            
        except OasisApiError as err:
            raise HomeAssistantError(
                f"Failed to set mode: {err.title} - {err.detail}"
            ) from err


    # --- SET TEMPERATURE ------------------------------------------------------
    
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Determina quale setpoint aggiornare in base alla modalità corrente
        current_mode = self.hvac_mode
        payload = {}

        if current_mode == HVACMode.COOL:
            payload["cool_setpoint"] = temp
        else:
            # Per HEAT e AUTO aggiorniamo heat_setpoint
            payload["heat_setpoint"] = temp

        try:
            _LOGGER.debug("Setting temperature for %s: %s", self._device_id, payload)
            await self.coordinator.client.thermostats.update_state(
                self._device_id, payload
            )
            await self.coordinator.async_request_refresh()
            
        except OasisApiError as err:
            raise HomeAssistantError(
                f"Failed to set temperature: {err.title} - {err.detail}"
            ) from err

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        # Nota: La rimozione dell'entità non cancella il dispositivo dal backend.
        # Quella operazione è gestita via Options Flow.
        pass