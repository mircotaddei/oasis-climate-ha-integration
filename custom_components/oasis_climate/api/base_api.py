"""Base class for OASIS API sub-clients."""
import logging
import aiohttp
from typing import Any

_LOGGER = logging.getLogger(__name__)

class OasisBaseApi:
    """Base class handling HTTP requests and authentication."""

    def __init__(self, session: aiohttp.ClientSession, api_url: str, api_key: str) -> None:
        """Initialize the base API."""
        self._session = session
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key


    # --- REQUEST --------------------------------------------------------------

    async def _request(self, method: str, endpoint: str, data: dict | None = None) -> Any:
        """Execute an HTTP request."""
        url = f"{self._api_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self._api_key,
        }

        try:
            async with self._session.request(
                method, url, headers=headers, json=data, timeout=10
            ) as response:
                
                if response.status in (402, 403):
                    # TODO: Handle this error
                    body = await response.json()
                    if body.get("code") == "TIER_LIMIT":
                        raise OasisTierLimitError(
                            body.get("message", "Tier limit reached"),
                            body.get("upgrade_url", "https://oasis.climate/upgrade") # URL ipotetico
                        )

                elif response.status in (200, 201, 202, 204):
                    # Handle 204 No Content
                    if response.status == 204:
                        return True
                    # Handle empty bodies
                    try:
                        return await response.json()
                    except Exception:
                        return True
                
                # Log error but don't crash
                text = await response.text()
                _LOGGER.error(
                    "OASIS API Error [%s] %s - Status: %s - Body: %s",
                    method, url, response.status, text
                )
                return None

        except aiohttp.ClientError as err:
            _LOGGER.error("OASIS API Connection Error: %s", err)
            return None


# --- OASIS TIER LIMIT ERROR ---------------------------------------------------

class OasisTierLimitError(Exception):
    """Exception raised when a tier limit is reached."""
    def __init__(self, message: str, upgrade_url: str = ""):
        self.message = message
        self.upgrade_url = upgrade_url
        super().__init__(message)