"""Config flow for OASIS Climate integration."""
import logging
from typing import Any, Dict
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import OasisApiClient, OasisApiAuthError, OasisApiConnectionError, OasisApiError
from .const import (
    DOMAIN, 
    CONF_API_KEY, 
    CONF_HOME_ID,
    CONF_HOME_NAME,
    CONF_API_URL,
    DEFAULT_API_URL
)

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OASIS Climate."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._api_key: str | None = None
        self._client: OasisApiClient | None = None
        self._existing_homes: list[dict] = []
        self._ha_location_data: dict = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Handle the initial step (API Key input)."""
        errors = {}

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            
            # Initialize API Client
            session = async_get_clientsession(self.hass)
            self._client = OasisApiClient(session, self._api_key)

            try:
                # Validate Key and fetch homes
                self._existing_homes = await self._client.async_get_homes()
                
                # Collect HA location data for next steps
                self._ha_location_data = {
                    "name": self.hass.config.location_name,
                    "latitude": self.hass.config.latitude,
                    "longitude": self.hass.config.longitude,
                    "timezone": self.hass.config.time_zone
                }

                # Decision Logic
                if not self._existing_homes:
                    return await self.async_step_create_new_home()
                else:
                    return await self.async_step_check_alignment()

            except OasisApiAuthError:
                errors["base"] = "invalid_auth"
            except OasisApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors
        )

    async def async_step_create_new_home(self, user_input=None):
        """
        Scenario A: No homes found. Confirm creation of a new home using HA data.
        """
        errors = {}
        
        if user_input is not None:
            try:
                # Create home on backend
                new_home = await self._client.async_create_home(self._ha_location_data)
                
                return self.async_create_entry(
                    title=new_home["name"],
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_HOME_ID: new_home["id"],
                        CONF_HOME_NAME: new_home["name"]
                    }
                )
            except OasisApiError as e:
                errors["base"] = "creation_failed"
                _LOGGER.error(f"Creation failed: {e}")

        # Show confirmation form
        return self.async_show_form(
            step_id="create_new_home",
            description_placeholders={
                "ha_name": self._ha_location_data["name"]
            },
            data_schema=vol.Schema({}) # Just a confirm button
        )

    async def async_step_check_alignment(self, user_input=None):
        """
        Scenario B: Homes exist. Ask to align (update) or create new.
        """
        errors = {}
        
        # We take the first home found for simplicity in this iteration
        # In a more complex scenario, we could let the user choose from a list
        target_home = self._existing_homes[0]

        if user_input is not None:
            choice = user_input.get("action")
            
            try:
                if choice == "align":
                    # Update existing home with HA data
                    updated_home = await self._client.async_update_home(
                        target_home["id"], 
                        self._ha_location_data
                    )
                    return self.async_create_entry(
                        title=updated_home["name"],
                        data={
                            CONF_API_KEY: self._api_key,
                            CONF_HOME_ID: updated_home["id"],
                            CONF_HOME_NAME: updated_home["name"]
                        }
                    )
                
                elif choice == "create_new":
                    # Try to create a new home (Backend will check Tier limits)
                    new_home = await self._client.async_create_home(self._ha_location_data)
                    return self.async_create_entry(
                        title=new_home["name"],
                        data={
                            CONF_API_KEY: self._api_key,
                            CONF_HOME_ID: new_home["id"],
                            CONF_HOME_NAME: new_home["name"]
                        }
                    )
            
            except OasisApiError as e:
                # Likely a Tier limit error or validation error
                errors["base"] = "api_error"
                # We can inject the error message from backend if needed
                return self.async_show_form(
                    step_id="check_alignment",
                    description_placeholders={
                        "remote_name": target_home["name"],
                        "ha_name": self._ha_location_data["name"],
                        "error_detail": str(e)
                    },
                    data_schema=self._get_alignment_schema(),
                    errors=errors
                )

        return self.async_show_form(
            step_id="check_alignment",
            description_placeholders={
                "remote_name": target_home["name"],
                "ha_name": self._ha_location_data["name"],
                "error_detail": ""
            },
            data_schema=self._get_alignment_schema(),
            errors=errors
        )

    def _get_alignment_schema(self):
        """Helper to build the choice schema."""
        return vol.Schema({
            vol.Required("action", default="align"): vol.In({
                "align": "Yes, update remote home with local data",
                "create_new": "No, create a new home"
            })
        })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        # We will implement OptionsFlow later for Thermostat CRUD
        # For now, return an empty handler to avoid errors
        return OasisOptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return self.async_create_entry(title="", data={})
    

class OasisOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for OASIS Climate."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: Show Tier info and start configuration wizard."""
        
        # If user_input is not None, the user clicked "Submit/Next"
        if user_input is not None:
            # Move to the next step of the wizard (Home selection)
            return await self.async_step_home()

        # Retrieve the API client instance
        client = self.hass.data[DOMAIN][self.config_entry.entry_id]["api_client"]
        
        # Fetch user info from the API
        user_info = await client.async_get_user_info()

        if not user_info:
            return self.async_abort(reason="cannot_connect")

        # Prepare data for the UI
        placeholders = {
            "user_email": user_info.get("email", "N/A"),
            "tier_name": user_info.get("tier", {}).get("name", "N/A"),
            "max_homes": str(user_info.get("tier", {}).get("max_homes", "N/A")),
        }

        # Return an empty schema. This renders a screen with the description 
        # (containing our placeholders) and a "Submit" button to proceed.
        return self.async_show_form(
            step_id="init",
            description_placeholders=placeholders,
            data_schema=vol.Schema({})
        )

    async def async_step_home(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Select the Home."""
        
        if user_input is not None:
            # Save the selected home in the options and finish (for now)
            # In the next phases, this will redirect to async_step_thermostat
            return self.async_create_entry(title="", data=user_input)

        # TODO: Here we will call client.async_get_homes()
        # For now, we put a dummy field to prove the wizard moves forward
        data_schema = vol.Schema({
            vol.Required("selected_home", default="My Home"): str
        })

        return self.async_show_form(
            step_id="home",
            data_schema=data_schema
        )