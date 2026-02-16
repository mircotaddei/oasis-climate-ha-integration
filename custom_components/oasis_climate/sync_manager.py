"""Manager for synchronizing HA registry events with the OASIS backend."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.core import Event, HomeAssistant # type: ignore
from homeassistant.helpers import device_registry as dr, entity_registry as er # type: ignore

from .api.client import OasisApiClient
from .const import DOMAIN
from .coordinator import OasisUpdateCoordinator
from .api.base_api import OasisApiError

_LOGGER = logging.getLogger(__name__)


# --- SETUP LISTENERS ----------------------------------------------------------

def setup_listeners(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: OasisApiClient,
    coordinator: OasisUpdateCoordinator,
) -> None:
    """
    Register listeners for device and entity registry updates.
    This function is called once from __init__.py.
    """

    # --- ON DEVICE UPDATE -----------------------------------------------------

    async def _on_device_update(event: Event) -> None:
        """Handle device registry updates, primarily for thermostat renames."""
        if event.data.get("action") != "update":
            return

        dev_reg = dr.async_get(hass)
        device_id = event.data.get("device_id")
        device = dev_reg.async_get(device_id)

        # Ensure the device belongs to our integration
        if not device or entry.entry_id not in device.config_entries:
            return

        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith("thermostat_"):
                try:
                    t_id = int(identifier.split("_")[1])
                    new_name = device.name_by_user or device.name

                    # Compare with coordinator data to prevent update loops
                    current_thermostat = coordinator.data.get("thermostats", {}).get(t_id)
                    if current_thermostat and current_thermostat["name"] != new_name:
                        _LOGGER.info(
                            "Syncing thermostat rename to backend: ID %s -> '%s'",
                            t_id,
                            new_name,
                        )
                        await client.thermostats.update_config(t_id, {"name": new_name})
                        # Request a refresh to get the latest state from backend
                        await coordinator.async_request_refresh()

                except (OasisApiError) as err:
                    _LOGGER.error("Rename failed on backend: {err.detail}")
                except (IndexError, ValueError):
                    _LOGGER.error(
                        "Failed to parse thermostat ID from identifier: %s", identifier
                    )
                break  # Identifier found, no need to check others

    async def _on_entity_update(event: Event) -> None:
        """Handle entity registry updates, primarily for sensor renames."""
        if event.data.get("action") != "update":
            return

        ent_reg = er.async_get(hass)
        entity_id = event.data.get("entity_id")
        entity_entry = ent_reg.async_get(entity_id)

        # Ensure the entity belongs to our integration and is a sensor
        if not entity_entry or entity_entry.platform != DOMAIN or not entity_entry.device_id.startswith("oasis_sensor_"):
            return

        try:
            s_id = int(entity_entry.device_id.split("_")[2])
            new_name = entity_entry.name or entity_entry.original_name

            # Find the sensor in coordinator data to get its current name
            current_name = None
            for t_data in coordinator.data.get("thermostats", {}).values():
                sensor_data = t_data.get("sensors_map", {}).get(s_id)
                if sensor_data:
                    current_name = sensor_data.get("name")
                    break
            
            if current_name is not None and current_name != new_name:
                _LOGGER.info(
                    "Syncing sensor rename to backend: ID %s -> '%s'", s_id, new_name
                )
                await client.sensors.update(s_id, {"name": new_name})
                await coordinator.async_request_refresh()

        except (OasisApiError) as err:
            _LOGGER.error("Rename failed on backend: {err.detail}")
        except (IndexError, ValueError) as e:
            _LOGGER.error("Error processing sensor rename event: %s", e)

    # Register the listeners and ensure they are cleaned up on unload
    entry.async_on_unload(
        hass.bus.async_listen("device_registry_updated", _on_device_update)
    )
    entry.async_on_unload(
        hass.bus.async_listen("entity_registry_updated", _on_entity_update)
    )