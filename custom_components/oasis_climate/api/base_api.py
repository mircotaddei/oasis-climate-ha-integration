"""Base class for OASIS API sub-clients."""
import logging
import aiohttp
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)


# --- OASIS API ERRORS --------------------------------------------------------

class OasisApiError(Exception):
    """
    Exception raised for backend API errors (RFC 7807 compliant).
    Includes specific backend codes and request IDs for debugging.
    """
    def __init__(
        self, 
        status: int, 
        title: str, 
        detail: str, 
        code: Optional[str] = None, 
        request_id: Optional[str] = None
    ):
        self.status = status
        self.title = title
        self.detail = detail
        self.code = code
        self.request_id = request_id
        
        # Costruiamo un messaggio di log completo
        msg = f"[{status}] {title}: {detail}"
        if code:
            msg += f" (Code: {code})"
        if request_id:
            msg += f" [ReqID: {request_id}]"
            
        super().__init__(msg)


# --- OASIS BASE API ----------------------------------------------------------

class OasisBaseApi:
    """Base class handling HTTP requests and authentication."""

    def __init__(self, session: aiohttp.ClientSession, api_url: str, api_key: str) -> None:
        """Initialize the base API."""
        self._session = session
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key


    # --- REQUEST ---------------------------------------------------------------

    async def _request(self, method: str, endpoint: str, data: dict | None = None) -> Any:
        """Execute an HTTP request with robust error handling."""
        url = f"{self._api_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self._api_key,
        }

        try:
            async with self._session.request(
                method, url, headers=headers, json=data, timeout=10 # type: ignore
            ) as response:
                
                # --- GESTIONE ERRORI (4xx, 5xx) ---
                if response.status >= 400:
                    content_type = response.headers.get("Content-Type", "")
                    
                    # 1. Se è JSON (application/json o application/problem+json)
                    if "json" in content_type:
                        try:
                            body = await response.json()
                            # Parsing RFC 7807 + Estensioni Custom
                            title = body.get("title") or f"HTTP {response.status}"
                            detail = body.get("detail") or "Unknown error occurred."
                            code = body.get("code") # Codice interno (es. AUTH-001)
                            req_id = body.get("request_id")
                            
                            raise OasisApiError(response.status, title, detail, code, req_id)
                        except ValueError:
                            # Header dice JSON ma il body è corrotto
                            pass

                    # 2. Fallback per HTML o Testo Semplice (es. 404 di Nginx, 502 Bad Gateway)
                    try:
                        text = await response.text()
                        # Tronchiamo se è una pagina HTML gigante
                        preview = text[:200] + "..." if len(text) > 200 else text
                    except Exception:
                        preview = "Unreadable response body."

                    # Solleviamo un errore generico basato sullo status
                    raise OasisApiError(
                        status=response.status,
                        title=f"HTTP Error {response.status}",
                        detail=f"Server returned non-JSON response: {preview}",
                        code="HTTP_ERROR"
                    )

                # --- GESTIONE SUCCESSO (2xx) ---
                if response.status == 204:
                    return True
                
                try:
                    return await response.json()
                except Exception:
                    # Body vuoto o non valido su una 200 OK
                    return True

        except aiohttp.ClientError as err:
            # Errori di connessione (DNS, Timeout, Connection Refused)
            _LOGGER.error("OASIS Connection Error: %s", err)
            raise OasisApiError(
                status=0,
                title="Connection Error",
                detail=f"Cannot connect to server: {str(err)}",
                code="CONNECTION_ERROR"
            ) from err