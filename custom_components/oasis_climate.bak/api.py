"""API Client for OASIS Climate."""
from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime
from typing import Any, List, Dict

import aiohttp
import async_timeout

from .const import DEFAULT_API_URL

_LOGGER = logging.getLogger(__name__)

class OasisApiClientError(Exception):
    """Exception to indicate a general API error."""

class OasisApiConnectionError(OasisApiClientError):
    """Exception to indicate a communication error."""

class OasisApiAuthError(OasisApiClientError):
    """Exception to indicate an authentication error."""

class OasisApiError(OasisApiClientError):
    """Exception to indicate a generic API error (e.g. 400, 500)."""

class OasisApiClient:
    """API Client for OASIS Climate Backend V2."""

    def __init__(
        self, 
        session: aiohttp.ClientSession | None = None,
        api_url: str = DEFAULT_API_URL,
        api_key: str = DEFAULT_API_URL
    ) -> None:
        """Initialize the API client."""
        
        self._session = session
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def async_validate_api_key(self) -> bool:
        """Validate the API key by fetching the thermostat list."""
        try:
            await self.async_get_thermostats()
            return True
        except OasisApiAuthError:
            return False
        except Exception:
            return False

    # --- HOME MANAGEMENT ---

    async def async_get_homes(self) -> List[Dict[str, Any]]:
        """
        Get the list of homes associated with the user.
        """
        return await self._request("GET", "/homes")

    async def async_create_home(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new home.
        Payload should match HomeCreate schema (name, latitude, longitude, timezone).
        """
        return await self._request("POST", "/homes", json_data=payload)

    async def async_update_home(self, home_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing home (Alignment).
        Payload should match HomeUpdate schema.
        """
        return await self._request("PUT", f"/homes/{home_id}", json_data=payload)

    # --- THERMOSTAT & TELEMETRY ---

    async def async_get_thermostats(self) -> List[Dict[str, Any]]:
        """
        Get the list of thermostats available for this user.
        Used in Config Flow for discovery.
        """
        return await self._request("GET", "/thermostats")

    async def async_push_telemetry(self, device_id: str, readings: List[Dict[str, Any]]) -> bool:
        """
        Push telemetry data using the V2 Schema (Nested Readings).
        
        Args:
            device_id: The hardware ID of the thermostat.
            readings: A list of dicts, e.g.:
                      [
                        {"unique_id": "temp_in", "value": 20.5},
                        {"unique_id": "boiler_status", "value": 1.0}
                      ]
        """
        payload = {
            "device_id": device_id,
            # Timestamp is added by backend if missing, or we can add it here
            "timestamp": datetime.utcnow().isoformat(),
            "readings": readings
        }
        
        try:
            await self._request("POST", "/telemetry/", json_data=payload)
            return True
        except Exception as e:
            _LOGGER.error("Error pushing telemetry: %s", e)
            return False

    async def async_get_latest_advice(self, thermostat_id: int) -> Dict[str, Any] | None:
        """
        Get the latest advice for a specific thermostat.
        Requires the Database ID (int), not the Device ID.
        """
        try:
            return await self._request("GET", f"/advice/{thermostat_id}/latest")
        except Exception as e:
            # Advice is optional, don't crash if missing
            _LOGGER.debug("No advice found or error fetching advice: %s", e)
            return None

    async def async_submit_feedback(self, thermostat_id: int, advice_id: int, response: str) -> bool:
        """Submit user feedback for an advice."""
        payload = {"response": response}
        try:
            await self._request("POST", f"/advice/{thermostat_id}/feedback/{advice_id}", json_data=payload)
            return True
        except Exception as e:
            _LOGGER.error("Error submitting feedback: %s", e)
            return False

    # --- INTERNAL ---

    async def _request(self, method: str, endpoint: str, json_data: dict | None = None) -> Any:
        """Execute the HTTP request."""
        url = f"{self._api_url}{endpoint}"
        
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method, 
                    url, 
                    headers=self._headers, 
                    json=json_data
                )
                
                if response.status == 401 or response.status == 403:
                    raise OasisApiAuthError("Invalid API Key")
                
                if response.status >= 400:
                    # Try to get error message from body
                    try:
                        err_body = await response.json()
                        detail = err_body.get("detail", response.reason)
                    except:
                        detail = response.reason
                    raise OasisApiError(f"API Error {response.status}: {detail}")
                
                # Handle 204 No Content
                if response.status == 204:
                    return None
                    
                return await response.json()

        except asyncio.TimeoutError as exception:
            raise OasisApiConnectionError("Timeout connecting to OASIS Cloud") from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise OasisApiConnectionError("Error connecting to OASIS Cloud") from exception