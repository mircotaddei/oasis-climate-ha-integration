"""API Handler for Thermostat operations."""
from typing import Any
from .base_api import OasisBaseApi


# --- THERMOSTAT API ----------------------------------------------------------

class ThermostatApi(OasisBaseApi):
    """Handles thermostat-related endpoints."""

    # --- CREATE ---------------------------------------------------------------

    async def create(self, home_id: int, name: str, local_id: str| None = None) -> dict[str, Any] | None:
        """
        Create a new thermostat in a home.
        
        :param home_id: The database ID of the home.
        :param name: The friendly name of the zone.
        :param local_id: The unique ID within Home Assistant (e.g., UUID).
        """
        payload = {
            "name": name,
            # "local_id": local_id,
            "local_id": name,
            "integration_source": "HA"
        }
        # Endpoint: POST /homes/{home_id}/devices
        return await self._request("POST", f"/homes/{home_id}/devices", data=payload)

    # --- DELETE ---------------------------------------------------------------

    async def delete(self, thermostat_id: str) -> bool:
        """Delete a thermostat."""
        # Assuming the backend accepts the string ID or DB ID here. 
        # If backend requires DB ID (int) for DELETE, this might need adjustment.
        result = await self._request("DELETE", f"/devices/{thermostat_id}")
        return result is not None

    # --- UPDATE STATE ---------------------------------------------------------

    async def update_state(self, thermostat_id: str, data: dict[str, Any]) -> bool:
        """Update operational state (setpoint, mode)."""
        result = await self._request("PATCH", f"/devices/{thermostat_id}/state", data=data)
        return result is not None

    # --- UPDATE CONFIG --------------------------------------------------------
    
    async def update_config(self, thermostat_id: str, data: dict[str, Any]) -> bool:
        """Update configuration (name, settings)."""
        result = await self._request("PATCH", f"/devices/{thermostat_id}/config", data=data)
        return result is not None

    # --- GET CLOUD CONFIG (TELEMETRY) -----------------------------------------

    async def get_cloud_config(self, device_id: str) -> dict[str, Any] | None:
        """
        Fetch cloud configuration using the telemetry endpoint.
        
        :param device_id: The globally unique hardware ID (string).
        """
        payload = {"device_id": device_id}
        # Endpoint: POST /api/v1/telemetry/config
        return await self._request("POST", "/telemetry/config", data=payload)