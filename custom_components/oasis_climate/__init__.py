"""Initialization of the OASIS Climate integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.const import Platform  # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers import device_registry as dr # type: ignore
from homeassistant.helpers.aiohttp_client import async_get_clientsession # type: ignore

from .const import DOMAIN, CONF_API_URL, CONF_API_KEY, CONF_HOME_ID
from .api.client import OasisApiClient
from .coordinator import OasisUpdateCoordinator
from .telemetry_manager import TelemetryManager
from . import sync_manager


_LOGGER = logging.getLogger(__name__)

# Supported platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE, 
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OASIS Climate from a config entry."""
    
    # 1. Initialize API Client
    client = OasisApiClient(
        session=async_get_clientsession(hass),
        api_url=entry.data[CONF_API_URL],
        api_key=entry.data[CONF_API_KEY]
    )
    
    # 2. Initialize Coordinator
    coordinator = OasisUpdateCoordinator(hass, client, entry)
    
    # Fetch initial data (blocking here is fine/expected for first load)
    await coordinator.async_config_entry_first_refresh()

    # 3. Initialize Telemetry Manager
    telemetry_manager = TelemetryManager(hass, client, coordinator, entry)

    # 4. Store instances
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": client,
        "coordinator": coordinator,
        "telemetry_manager": telemetry_manager,
    }

    # 5. Synchronize devices with the backend (Device Registry)
    _sync_thermostat_devices(hass, entry, coordinator)

    # 6. Load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 7. Start Telemetry (NON-BLOCKING)
    # Usiamo async_create_background_task per evitare che HA resti in "Starting..."
    # se la telemetria impiega tempo o se ci sono sensori non ancora pronti.
    entry.async_create_background_task(
        hass, telemetry_manager.async_start(), "oasis_telemetry_start"
    )

    # 8. Setup listeners
    sync_manager.setup_listeners(hass, entry, client, coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


# --- SYNC THERMOSTAT DEVICES -------------------------------------------------

def _sync_thermostat_devices(hass: HomeAssistant, entry: ConfigEntry, coordinator: OasisUpdateCoordinator) -> None:
    """
    Synchronize Home and Thermostat devices from the backend to the HA Device Registry.
    Uses device_id (string) as the unique identifier.
    """
    dev_reg = dr.async_get(hass)
    
    home_data = coordinator.data.get("home", {})
    home_id = str(entry.data[CONF_HOME_ID])
    
    if home_data:
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"home_{home_id}")},
            name=home_data.get("name", "OASIS Home"),
            manufacturer="OASIS Climate",
            model="Smart Home Controller",
            configuration_url=entry.data[CONF_API_URL].replace("/api/v1", "")
        )

    backend_thermostats = coordinator.data.get("thermostats", {})
    expected_identifiers = {f"thermostat_{t_dev_id}" for t_dev_id in backend_thermostats.keys()}
    expected_identifiers.add(f"home_{home_id}")

    # Prune stale devices from Home Assistant
    current_devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in current_devices:
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith("thermostat_"):
                if identifier not in expected_identifiers:
                    _LOGGER.warning("Pruning stale device: %s (Name: %s)", identifier, device.name)
                    dev_reg.async_remove_device(device.id)
                break 

    # Create/Update Thermostats
    for t_dev_id, t_data in backend_thermostats.items():
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"thermostat_{t_dev_id}")},
            name=t_data["name"],
            manufacturer="OASIS Climate",
            model="Thermostat Zone",
            sw_version=t_data.get("agent_version", "1.0"),
            via_device=(DOMAIN, f"home_{home_id}")
        )


# --- UNLOAD ENTRY ------------------------------------------------------------

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of the integration."""
    # Stop telemetry cleanly
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data and "telemetry_manager" in data:
        data["telemetry_manager"].async_stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# --- REMOVE ENTRY ------------------------------------------------------------

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of the integration."""
    client = OasisApiClient(
        session=async_get_clientsession(hass),
        api_url=entry.data[CONF_API_URL],
        api_key=entry.data[CONF_API_KEY]
    )
    home_id = entry.data.get(CONF_HOME_ID)
    
    if home_id:
        try:
            # TODO remove when dashboard will be done
            _LOGGER.info("Integration removed. Deleting Home %s from backend.", home_id)
            await client.homes.delete(home_id)
            _LOGGER.info("OASIS Integration removed. Backend data preserved.")
        except Exception as e:
            _LOGGER.warning("Failed to delete home from backend: %s", e)


# --- UPDATE LISTENER ---------------------------------------------------------

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)