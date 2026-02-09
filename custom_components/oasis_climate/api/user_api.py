"""API Handler for User operations."""
from typing import Any
from .base_api import OasisBaseApi

class UserApi(OasisBaseApi):
    """Handles user-related endpoints."""


    # --- GET ME ----------------------------------------------------------------
    
    async def get_me(self) -> dict[str, Any] | None:
        """Fetch current user info and tier."""
        return await self._request("GET", "/users/me")
