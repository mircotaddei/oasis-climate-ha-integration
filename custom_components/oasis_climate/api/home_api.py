"""API Handler for Home operations."""
from typing import Any
from .base_api import OasisBaseApi

class HomeApi(OasisBaseApi):
    """Handles home-related endpoints."""

    # --- LIST -----------------------------------------------------------------

    async def list(self) -> list[dict[str, Any]] | None:
        """List all homes."""
        data = await self._request("GET", "/homes")
        return data if isinstance(data, list) else None


    # --- CREATE ---------------------------------------------------------------

    async def create(self, name: str) -> dict[str, Any] | None:
        """Create a new home."""
        return await self._request("POST", "/homes", data={"name": name})


    # --- DELETE ---------------------------------------------------------------

    async def delete(self, home_id: int) -> bool:
        """Delete a home."""
        result = await self._request("DELETE", f"/homes/{home_id}")
        return result is not None
