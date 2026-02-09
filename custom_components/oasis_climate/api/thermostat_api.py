"""API Handler for Thermostat operations."""
from typing import Any
from .base_api import OasisBaseApi

class ThermostatApi(OasisBaseApi):
    """Handles thermostat-related endpoints."""


    # --- CREATE ---------------------------------------------------------------

    async def create(self, home_id: int, name: str) -> dict[str, Any] | None:
        """Create a new thermostat in a home."""
        return await self._request("POST", f"/homes/{home_id}/devices", data={"name": name})


    # --- DELETE ---------------------------------------------------------------

    async def delete(self, thermostat_id: int) -> bool:
        """Delete a thermostat."""
        result = await self._request("DELETE", f"/devices/{thermostat_id}")
        return result is not None


    # --- UPDATE STATE ---------------------------------------------------------

    async def update_state(self, thermostat_id: int, data: dict[str, Any]) -> bool:
        """Update operational state (setpoint, mode)."""
        result = await self._request("PATCH", f"/devices/{thermostat_id}/state", data=data)
        return result is not None


    # --- UPDATE CONFIG --------------------------------------------------------
    
    async def update_config(self, thermostat_id: int, data: dict[str, Any]) -> bool:
        """Update configuration (name, settings)."""
        result = await self._request("PATCH", f"/devices/{thermostat_id}/config", data=data)
        return result is not None
