"""API Handler for Sensor operations."""
from typing import Any
from .base_api import OasisBaseApi


# --- SENSOR API ---------------------------------------------------------------

class SensorApi(OasisBaseApi):
    """Handles sensor-related endpoints."""


    # --- LIST BY THERMOSTAT ---------------------------------------------------

    async def list_by_thermostat(self, thermostat_id: str) -> list[dict[str, Any]] | None:
        """List sensors for a specific thermostat."""
        data = await self._request("GET", f"/devices/{thermostat_id}/sensors")
        return data if isinstance(data, list) else None


    # --- CREATE ---------------------------------------------------------------

    async def create(self, thermostat_id: str, entity_id: str, sensor_type: str, name: str) -> dict[str, Any] | None:
        """Map a new sensor to a thermostat."""
        payload = {
            "local_id": entity_id,
            "integration_source": "ha",
            "type": sensor_type,
            "name": name,
            "is_virtual": False,
            "meta": {}
        }
        return await self._request("POST", f"/devices/{thermostat_id}/sensors", data=payload)


    # --- DELETE ---------------------------------------------------------------

    async def delete(self, sensor_id: str) -> bool:
        """Delete a sensor mapping."""
        result = await self._request("DELETE", f"/sensors/{sensor_id}")
        return result is not None


    # --- UPDATE ---------------------------------------------------------------
    
    async def update(self, sensor_id: str, data: dict[str, Any]) -> bool:
        """Update sensor details (e.g., name)."""
        result = await self._request("PATCH", f"/sensors/{sensor_id}", data=data)
        return result is not None


    # --- SEND TELEMETRY -------------------------------------------------------

    async def send_telemetry(self, telemetry_payload: dict[str, Any]) -> dict[str, Any] | None:
        """Send a batch of sensor readings to the backend."""
        return await self._request("POST", "/telemetry", data=telemetry_payload)