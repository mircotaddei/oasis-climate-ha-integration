"""API Handler for Sensor operations."""
from typing import Any
from .base_api import OasisBaseApi

class SensorApi(OasisBaseApi):
    """Handles sensor-related endpoints."""


    # --- LIST BY THERMOSTAT ---------------------------------------------------

    async def list_by_thermostat(self, thermostat_id: int) -> list[dict[str, Any]] | None:
        """List sensors for a specific thermostat."""
        data = await self._request("GET", f"/devices/{thermostat_id}/sensors")
        return data if isinstance(data, list) else None


    # --- CREATE ---------------------------------------------------------------

    async def create(self, thermostat_id: int, entity_id: str, sensor_type: str, name: str) -> dict[str, Any] | None:
        """Map a new sensor to a thermostat."""
        payload = {
            "local_id": entity_id,
            "integration_source": "ha",
            "name": name,
            "type": sensor_type
        }
        return await self._request("POST", f"/devices/{thermostat_id}/sensors", data=payload)


    # --- DELETE ---------------------------------------------------------------

    async def delete(self, sensor_id: int) -> bool:
        """Delete a sensor mapping."""
        result = await self._request("DELETE", f"/sensors/{sensor_id}")
        return result is not None


    # --- UPDATE ---------------------------------------------------------------
    
    async def update(self, sensor_id: int, data: dict[str, Any]) -> bool:
        """Update sensor details (e.g., name)."""
        # Endpoint: PATCH /sensors/{id}
        result = await self._request("PATCH", f"/sensors/{sensor_id}", data=data)
        return result is not None