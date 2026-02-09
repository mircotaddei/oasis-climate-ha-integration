"""Initialization of the OASIS Climate integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.const import Platform # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers import device_registry as dr # type: ignore
from homeassistant.helpers.aiohttp_client import async_get_clientsession # type: ignore

from .const import DOMAIN, CONF_API_URL, CONF_API_KEY, CONF_HOME_ID
from .api.client import OasisApiClient
from .coordinator import OasisUpdateCoordinator
from . import sync_manager


_LOGGER = logging.getLogger(__name__)

# Supported platforms
PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OASIS Climate from a config entry."""
    
    # 1. Initialize API Client and Data Coordinator
    client = OasisApiClient(
        session=async_get_clientsession(hass),
        api_url=entry.data[CONF_API_URL],
        api_key=entry.data[CONF_API_KEY]
    )
    coordinator = OasisUpdateCoordinator(hass, client, entry)
    
    # 2. Fetch initial data from the backend
    await coordinator.async_config_entry_first_refresh()

    # 3. Store instances for platforms to use
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": client,
        "coordinator": coordinator,
    }

    # 4. Synchronize devices with the backend
    _sync_thermostat_devices(hass, entry, coordinator)

    # 5. Load platforms (climate, sensor) which will create entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 6. Set up listener for options updates (e.g., thermostat rename)
    sync_manager.setup_listeners(hass, entry, client, coordinator)

    # 7. Set up listener for options updates (e.g., adding a new thermostat)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


# --- SYNC THERMOSTAT DEVICES --------------------------------------------------

def _sync_thermostat_devices(hass: HomeAssistant, entry: ConfigEntry, coordinator: OasisUpdateCoordinator) -> None:
    """
    Synchronize Thermostat devices from the backend to the HA Device Registry.
    This function does NOT handle the Home device anymore.
    """
    dev_reg = dr.async_get(hass)
    _LOGGER.error("SYNC THERMOSTAT DEVICES NON DOVREBBE")
    _LOGGER.error("SYNC THERMOSTAT DEVICES NON DOVREBBE")
    _LOGGER.error("SYNC THERMOSTAT DEVICES NON DOVREBBE")
    # --- A. Get expected thermostat identifiers from the backend ---
    backend_thermostats = coordinator.data.get("thermostats", {})
    expected_identifiers = {f"thermostat_{t_id}" for t_id in backend_thermostats.keys()}

    # --- B. Prune stale devices from Home Assistant ---
    # Remove any device that is in HA but not in the backend's current list
    current_devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in current_devices:
        # A device identifier is a tuple, e.g., {('oasis_climate', 'thermostat_123')}
        # We check if any of its identifiers match our domain
        for domain, identifier in device.identifiers:
            if domain == DOMAIN:
                if identifier not in expected_identifiers:
                    _LOGGER.warning("Pruning stale device: %s (Name: %s)", identifier, device.name)
                    dev_reg.async_remove_device(device.id)
                break # Move to the next device

    # --- C. Create or Update thermostat devices in Home Assistant ---
    for t_id, t_data in backend_thermostats.items():
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"thermostat_{t_id}")},
            # Thermostats are now directly linked to the integration (ConfigEntry)
            # The 'via_device' parameter is removed.
            name=t_data["name"],
            manufacturer="OASIS Climate",
            model="Thermostat Zone",
            sw_version=t_data.get("agent_version", "1.0")
        )


# --- UNLOAD ENTRY -------------------------------------------------------------

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# --- REMOVE ENTRY ------------------------------------------------------------

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of the integration: delete the Home from the backend."""
    client = OasisApiClient(
        session=async_get_clientsession(hass),
        api_url=entry.data[CONF_API_URL],
        api_key=entry.data[CONF_API_KEY]
    )
    home_id = entry.data.get(CONF_HOME_ID)
    
    if home_id:
        _LOGGER.warning("Integration removed. Deleting Home %s from backend.", home_id)
        await client.homes.delete(home_id)


# --- UPDATE LISTENER ---------------------------------------------------------

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the integration."""
    await hass.config_entries.async_reload(entry.entry_id)