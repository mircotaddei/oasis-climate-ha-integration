"""DataUpdateCoordinator for OASIS Climate."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_HOME_ID
from .api.client import OasisApiClient

_LOGGER = logging.getLogger(__name__)

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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data and restructure it for easy access."""
        try:
            # 1. Fetch the full hierarchy for the user
            homes = await self.client.homes.list()
            if not homes:
                _LOGGER.warning("No homes found for this user.")
                return {}

            # 2. Find the specific home managed by this config entry
            # Ensure home_id is a string for consistent comparison
            home_id_str = str(self.entry.data[CONF_HOME_ID])
            selected_home = next(
                (h for h in homes if str(h.get("id")) == home_id_str), None
            )
            
            if not selected_home:
                _LOGGER.warning("Home ID %s not found in backend data.", home_id_str)
                return {}

            # 3. Restructure the data for efficient O(1) access in platforms
            # Final structure:
            # {
            #    "home": { ...home_data... },
            #    "thermostats": {
            #        t_id: {
            #            ...thermostat_data...,
            #            "sensors_map": { s_id: sensor_data }
            #        }
            #    }
            # }
            
            structured_data = {
                "home": selected_home,
                "thermostats": {}
            }

            for thermostat in selected_home.get("thermostats", []):
                t_id = thermostat["id"]
                
                # Create a map of sensors indexed by their ID for O(1) lookup
                sensors_map = {
                    sensor["id"]: sensor for sensor in thermostat.get("sensors", [])
                }
                
                # Add the map to the thermostat data
                thermostat["sensors_map"] = sensors_map
                
                # Add the thermostat to the main structure
                structured_data["thermostats"][t_id] = thermostat

            return structured_data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err