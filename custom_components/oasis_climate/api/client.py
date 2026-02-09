"""Main API Client for OASIS Climate."""
import aiohttp

from .user_api import UserApi
from .home_api import HomeApi
from .thermostat_api import ThermostatApi
from .sensor_api import SensorApi

class OasisApiClient:
    """
    Main container for OASIS API sub-clients.
    Uses Composition pattern to expose specialized APIs.
    """

    def __init__(
        self, 
        session: aiohttp.ClientSession, 
        api_url: str, 
        api_key: str
    ) -> None:
        """Initialize the client and its sub-components."""
        # Instantiate sub-clients
        self.user = UserApi(session, api_url, api_key)
        self.homes = HomeApi(session, api_url, api_key)
        self.thermostats = ThermostatApi(session, api_url, api_key)
        self.sensors = SensorApi(session, api_url, api_key)


    # --- VALIDATE AUTH -------------------------------------------------------

    async def async_validate_auth(self) -> bool:
        """Helper to validate authentication using the User API."""
        data = await self.user.get_me()
        return data is not None
