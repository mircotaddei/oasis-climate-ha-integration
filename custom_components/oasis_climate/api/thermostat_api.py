"""API Handler for Thermostat operations."""
from typing import Any
from .base_api import OasisBaseApi


# --- THERMOSTAT API -----------------------------------------------------------

class ThermostatApi(OasisBaseApi):
    """Handles thermostat-related endpoints."""


    # --- CREATE ---------------------------------------------------------------

    async def create(self, home_id: int, name: str, local_id: str) -> dict[str, Any] | None:
        """Create a new thermostat in a home."""
        payload = {
            "name": name,
            "local_id": local_id,
            "integration_source": "ha",
            "meta": {}
        }
        return await self._request("POST", f"/homes/{home_id}/devices", data=payload)


    # --- DELETE ---------------------------------------------------------------

    async def delete(self, device_id: str) -> bool:
        """Delete a thermostat."""
        result = await self._request("DELETE", f"/devices/{device_id}")
        return result is not None


    # --- UPDATE STATE ---------------------------------------------------------

    async def update_state(self, device_id: str, data: dict[str, Any]) -> bool:
        """Update operational state (setpoint, mode)."""
        result = await self._request("PATCH", f"/devices/{device_id}/state", data=data)
        return result is not None


    # --- UPDATE CONFIG --------------------------------------------------------
    
    async def update_config(self, device_id: str, data: dict[str, Any]) -> bool:
        """Update configuration (name, settings)."""
        result = await self._request("PATCH", f"/devices/{device_id}/config", data=data)
        return result is not None


    # --- GET CLOUD CONFIG -----------------------------------------------------

    async def get_cloud_config(self, device_id: str) -> dict[str, Any] | None:
        """Fetch cloud configuration using the telemetry endpoint."""
        payload = {"device_id": device_id}
        return await self._request("POST", "/telemetry/config", data=payload)