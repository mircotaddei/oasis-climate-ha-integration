"""API Handler for Telemetry operations."""
from typing import Any
from .base_api import OasisBaseApi


# --- TELEMETRY API -----------------------------------------------------------

class TelemetryApi(OasisBaseApi):
    """Handles telemetry and cloud config endpoints."""


    # --- SEND BATCH (POST /telemetry) -------------------------------
    async def send_batch(self, payload: dict[str, Any]) -> bool:
        """
        Send a batch of sensor readings.
        Payload must follow TelemetryData schema.
        """
        # Endpoint: POST /api/v1/telemetry
        result = await self._request("POST", "/telemetry", data=payload)
        return result is not None


    # --- GET CLOUD CONFIG (POST /telemetry/config) ----------------------------
    async def get_config(self, device_id: str) -> dict[str, Any] | None:
        """
        Request operational configuration for the device.
        """
        # Endpoint: POST /api/v1/telemetry/config
        # We send the device_id to identify which config we need
        payload = {"device_id": device_id}
        result = await self._request("POST", "/telemetry/config", data=payload)
        return result