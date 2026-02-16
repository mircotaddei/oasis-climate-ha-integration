"""DataUpdateCoordinator for OASIS Climate."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed # type: ignore

from .const import DOMAIN, CONF_HOME_ID
from .api.client import OasisApiClient
from .api.base_api import OasisApiError

_LOGGER = logging.getLogger(__name__)


# --- OASIS UPDATE COORDINATOR ------------------------------------------------

class OasisUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: OasisApiClient, entry: ConfigEntry) -> None:
        """Initialize."""
        self.client = client
        self.entry = entry
        self.home_id = str(entry.data[CONF_HOME_ID]) # Ensure string for comparison

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )


    # --- UPDATE DATA ----------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data and restructure it for easy access."""
        try:
            try:
                homes = await self.client.homes.list()
            except Exception as err:
                _LOGGER.error("API Call Failed: client.homes.list() - %s", err)
                raise

            if not homes:
                _LOGGER.warning("No homes found for this user.")
                return {}

            home_id_str = str(self.entry.data[CONF_HOME_ID])
            selected_home = next(
                (h for h in homes if str(h.get("id")) == home_id_str), None
            )
            
            if not selected_home:
                _LOGGER.warning("Home ID %s not found in backend data. Available homes: %s", home_id_str, [h.get("id") for h in homes])
                return {}

            structured_data = {
                "home": selected_home,
                "thermostats": {}
            }

            for thermostat in selected_home.get("thermostats", []):
                t_device_id = thermostat.get("device_id")
                if not t_device_id:
                    t_device_id = thermostat.get("unique_id")
                if not t_device_id:
                    t_device_id = str(thermostat.get("id"))
                
                thermostat["device_id"] = t_device_id

                # --- Fetch Cloud Config ---
                try:
                    cloud_config = await self.client.thermostats.get_cloud_config(t_device_id)
                    thermostat["cloud_config"] = cloud_config or {}
                except Exception as err:
                    _LOGGER.warning("Failed to fetch cloud config for thermostat %s: %s", t_device_id, err)
                    thermostat["cloud_config"] = {}

                # --- Process Sensors ---
                sensors_map = {}
                for sensor in thermostat.get("sensors", []):
                    s_device_id = sensor.get("device_id") or sensor.get("unique_id")
                    if not s_device_id:
                        s_device_id = str(sensor.get("id"))
                    
                    meta = sensor.get("meta")
                    if meta is None:
                        meta = {}
                        sensor["meta"] = meta

                    if "local_id" not in meta and "local_id" in sensor:
                        meta["local_id"] = sensor["local_id"]

                    sensors_map[s_device_id] = sensor
                
                thermostat["sensors_map"] = sensors_map
                structured_data["thermostats"][t_device_id] = thermostat

            return structured_data

        except OasisApiError as err:
            _LOGGER.error("OASIS API Error: %s - %s", err.title, err.detail)
            raise UpdateFailed(f"API Error - {err.title}: {err.detail}") from err
            
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching OASIS data")
            raise UpdateFailed(f"Error communicating with API: {type(err).__name__} - {err}") from err