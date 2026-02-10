"""Base class for OASIS API sub-clients."""
import logging
import aiohttp
from typing import Any

_LOGGER = logging.getLogger(__name__)


# --- OASIS API ERRORS ---

class OasisApiError(Exception):
    """Exception raised for backend API errors (RFC 7807)."""
    def __init__(self, title: str, detail: str):
        self.title = title
        self.detail = detail
        super().__init__(f"{title}: {detail}")


# --- OASIS BASE API ---

class OasisBaseApi:
    """Base class handling HTTP requests and authentication."""

    def __init__(self, session: aiohttp.ClientSession, api_url: str, api_key: str) -> None:
        """Initialize the base API."""
        self._session = session
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key

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
                
                # --- MODIFICA: Gestione Generica Errori RFC 7807 (4xx e 5xx) ---
                if response.status >= 400:
                    try:
                        body = await response.json()
                        # RFC 7807 standard fields
                        title = body.get("title", f"Error {response.status}")
                        detail = body.get("detail", "An unexpected error occurred.")
                    except Exception:
                        # Fallback se il body non è JSON valido
                        title = f"Error {response.status}"
                        detail = await response.text()

                    # Solleva sempre l'eccezione con i dettagli del backend
                    raise OasisApiError(title, detail)
                # ---------------------------------------------------------------

                if response.status in (200, 201, 202, 204):
                    if response.status == 204:
                        return True
                    try:
                        return await response.json()
                    except Exception:
                        return True
                
                return None

        except aiohttp.ClientError as err:
            _LOGGER.error("OASIS API Connection Error: %s", err)
            return None