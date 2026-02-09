"""Config flow for OASIS Climate integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries # type: ignore
from homeassistant.const import CONF_NAME # type: ignore
from homeassistant.core import HomeAssistant, callback # type: ignore
from homeassistant.data_entry_flow import FlowResult # type: ignore
from homeassistant.helpers.aiohttp_client import async_get_clientsession # type: ignore
from homeassistant.helpers import (selector, entity_registry as er, device_registry as dr,) # type: ignore

from .api.client import OasisApiClient
from .api.base_api import OasisTierLimitError
from .coordinator import OasisUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_API_URL,
    CONF_API_KEY,
    CONF_HOME_ID,
    DEFAULT_API_URL,
    SENSOR_TYPES,
    SENSOR_DEVICE_CLASSES
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
        vol.Required(CONF_API_KEY): str,
    }
)

class OasisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OASIS Climate."""

    VERSION = 0
    MAJOR_VERSION = 0
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._login_data: dict[str, Any] = {}
        self._client: OasisApiClient | None = None


    # --- STEP USER ------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: API Credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._login_data = user_input
            
            # Inizializza il client per verificare le credenziali
            session = async_get_clientsession(self.hass)
            self._client = OasisApiClient(
                session,
                user_input[CONF_API_URL],
                user_input[CONF_API_KEY],
            )

            try:
                # Verifica autenticazione
                if await self._client.async_validate_auth():
                    # Se ok, passa alla selezione della casa
                    return await self.async_step_select_home()
                else:
                    errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


    # --- STEP SELECT HOME -----------------------------------------------------

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle home selection or creation."""
        errors: dict[str, str] = {}

        try:
            homes = await self._client.homes.list()
        except Exception:
            return self.async_abort(reason="cannot_connect")

        if homes is None:
            return self.async_abort(reason="cannot_connect")

        # SCENARIO A: Nessuna casa esistente -> Creazione Automatica
        if not homes:
            return await self._create_home_automatically()

        # SCENARIO B: Case esistenti -> Selezione Utente
        options = {str(home["id"]): home["name"] for home in homes}
        options["CREATE_NEW"] = f"Create new home: {self.hass.config.location_name}"

        if user_input is not None:
            selected_val = user_input[CONF_HOME_ID]

            if selected_val == "CREATE_NEW":
                return await self._create_home_automatically()
            
            home_id = int(selected_val)
            home_name = options[selected_val]
            
            return self._async_create_entry(home_id, home_name)

        return self.async_show_form(
            step_id="select_home",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOME_ID): vol.In(options),
                }
            ),
            errors=errors,
        )


    # --- CREATE HOME AUTOMATICALLY --------------------------------------------

    async def _create_home_automatically(self) -> FlowResult:
        """Helper to create a home using HA instance name."""
        ha_name = self.hass.config.location_name
        try:
            new_home = await self._client.homes.create(name=ha_name) # TODO move to api package
            if not new_home:
                return self.async_abort(reason="creation_failed")
            
            return self._async_create_entry(new_home["id"], new_home["name"])
        except Exception:
            _LOGGER.exception("Error creating home")
            return self.async_abort(reason="creation_failed")


    # --- CREATE ENTRY ---------------------------------------------------------

    def _async_create_entry(self, home_id: int, home_name: str) -> FlowResult:
        """Finalize the config entry creation."""
        self._async_abort_entries_match({CONF_HOME_ID: home_id})

        data = {
            **self._login_data,
            CONF_HOME_ID: home_id,
            CONF_NAME: home_name
        }

        return self.async_create_entry(title=home_name, data=data)


    # --- GET OPTIONS FLOW -----------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OasisOptionsFlowHandler(config_entry)


# --- OASIS OPTIONS FLOW HANDLER -----------------------------------------------

class OasisOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Oasis (Thermostats & Sensors setup)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry_init = config_entry
        self._selected_thermostat_id: int | None = None
        self._selected_sensor_type_label: str | None = None
        self._action: str | None = None

    @property
    def _client(self) -> OasisApiClient:
        return self.hass.data[DOMAIN][self.config_entry.entry_id]["api_client"]

    @property
    def _coordinator(self) -> OasisUpdateCoordinator:
        return self.hass.data[DOMAIN][self.config_entry.entry_id]["coordinator"]

    @property
    def _home_id(self) -> int:
        return self.config_entry.data[CONF_HOME_ID]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options menu."""
        errors: dict[str, str] = {}

        if user_input is not None:
            action = user_input["action"]
            if action == "manage_sensors":
                return await self.async_step_sensor_thermostat_select()
            elif action == "add_thermostat":
                return await self.async_step_thermostat_add()
            elif action == "edit_thermostat":
                self._action = "edit"
                return await self.async_step_thermostat_select()
            elif action == "remove_thermostat":
                self._action = "remove"
                return await self.async_step_thermostat_select()
            elif action == "account_info":
                return await self.async_step_account_info()

        options = {
            "manage_sensors": "Manage Sensors",
            "add_thermostat": "Add new Thermostat",
            "edit_thermostat": "Rename Thermostat",
            "remove_thermostat": "Remove Thermostat",
            "account_info": "Account & Tier Info",
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(options),
                }
            ),
            errors=errors,
        )


    # --- STEP ACCOUNT INFO -----------------------------------------------------

    async def async_step_account_info(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Display user account info."""
        if user_input is not None:
            return await self.async_step_init()

        try:
            user_data = await self._client.user.get_me()
        except Exception:
            return self.async_abort(reason="cannot_connect")

        tier = user_data.get("tier", "Unknown") # type: ignore
        name = user_data.get("name", "Unknown") # type: ignore
        email = user_data.get("email", "Unknown") # type: ignore
        
        msg = (
            f"## Current Tier: **{tier.get("name", "Unknown")}**\n\n"
            f"### Account: {name} - {email} \n\n"
            f"**Max homes:** {tier.get("max_homes", "N/A")}\n"
            f"**Max thermostats:** {tier.get("max_thermostats_per_home", "N/A")}\n"
            f"**Max sensors per thermostat:** {tier.get("max_sensors_per_thermostat", "N/A")}\n"
            f"___\n"
            f"**Can control boiler:** {tier.get("can_control_boiler", "N/A")}\n"
            f"**Can modulate:** {tier.get("can_modulate", "N/A")}\n"
            f"**Can cool:** {tier.get("can_cool", "N/A")}\n"
            f"**Has offline intelligence:** {tier.get("has_offline_intelligence", "N/A")}\n"
            f"___\n"
            f"**Has energy optimization:** {tier.get("has_energy_optim", "N/A")}\n"
            f"**Has solar integration:** {tier.get("has_solar_integration", "N/A")}\n"
            f"**Has presence detection:** {tier.get("has_presence_detection", "N/A")}\n"
            f"**Has advanced anomalies:** {tier.get("has_advanced_anomalies", "N/A")}\n"
            f"___\n"
            f"**Has advanced dashboard:** {tier.get("has_advanced_dashboard", "N/A")}\n"
            f"**Has API access:** {tier.get("has_api_access", "N/A")}\n"
            f"___\n"
            f"**Telemetry Interval:** {tier.get("telemetry_interval_min", "N/A")} minutes\n"
            f"**Data Retention:** {tier.get("data_retention_days", "N/A")} days\n"
            f"___\n"
            f"[Go to Dashboard]({DEFAULT_API_URL.replace('/api/v1', '')}/dashboard)"
        )


        return self.async_show_form(
            step_id="account_info",
            data_schema=None, # No input fields, only "Next" button
            description_placeholders={"account_details": msg},
        )
    

    # --- STEP TIER ERROR --------------------------------------------------------

    async def async_step_tier_error(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Display a 'modal' for tier limits."""
        if user_input is not None:
            return await self.async_step_init()

        # Recupera il messaggio salvato in self (vedi punto successivo)
        error_msg = getattr(self, "_last_error_msg", "Unknown error")
        upgrade_url = getattr(self, "_last_upgrade_url", "#")

        msg = (
            f"### ⛔ Operation Denied\n\n"
            f"{error_msg}\n\n"
            f"To continue, you need to upgrade your plan.\n\n"
            f"[Upgrade Now]({upgrade_url})"
        )

        return self.async_show_form(
            step_id="tier_error",
            data_schema=vol.Schema({}),
            description_placeholders={"error_details": msg},
        )
    

    # --- THERMOSTAT CRUD -------------------------------------------------------
    

    # --- STEP THERMOSTAT ADD ---------------------------------------------------

    async def async_step_thermostat_add(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a new thermostat."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input["name"]
            try:
                await self._client.thermostats.create(self._home_id, name)
                # await self._coordinator.async_request_refresh()
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return await self.async_step_init()
            
            except OasisTierLimitError as err:
                self._last_error_msg = err.message
                self._last_upgrade_url = err.upgrade_url
                return await self.async_step_tier_error()
            
            except Exception:
                _LOGGER.exception("Error creating thermostat")
                errors["base"] = "api_error"

        return self.async_show_form(
            step_id="thermostat_add",
            data_schema=vol.Schema({vol.Required("name"): str}),
            errors=errors,
        )


    # --- STEP THERMOSTAT SELECT ------------------------------------------------

    async def async_step_thermostat_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a thermostat to edit or remove."""
        thermostats = self._coordinator.data.get("thermostats", {})
        if not thermostats:
            return self.async_abort(reason="no_thermostats")

        options = {str(t_id): t_data["name"] for t_id, t_data in thermostats.items()}

        if user_input is not None:
            self._selected_thermostat_id = int(user_input["thermostat_id"])
            if self._action == "edit":
                return await self.async_step_thermostat_edit()
            elif self._action == "remove":
                return await self.async_step_thermostat_remove()

        return self.async_show_form(
            step_id="thermostat_select",
            data_schema=vol.Schema({vol.Required("thermostat_id"): vol.In(options)}),
            description_placeholders={"action": self._action},
        )


    # --- STEP THERMOSTAT EDIT --------------------------------------------------

    async def async_step_thermostat_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Rename a thermostat."""
        errors: dict[str, str] = {}
        t_id = self._selected_thermostat_id

        if user_input is not None:
            new_name = user_input["name"]
            try:
                await self._client.thermostats.update_config(t_id, {"name": new_name}) # type: ignore
                await self._coordinator.async_request_refresh()
                return await self.async_step_init()
            except Exception:
                _LOGGER.exception("Error updating thermostat")
                errors["base"] = "api_error"

        current_name = self._coordinator.data["thermostats"][t_id]["name"]
        return self.async_show_form(
            step_id="thermostat_edit",
            data_schema=vol.Schema({vol.Required("name", default=current_name): str}),
            errors=errors,
        )


    # --- STEP THERMOSTAT REMOVE -------------------------------------------------

    async def async_step_thermostat_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove a thermostat."""
        if user_input is not None:
            try:
                await self._client.thermostats.delete(self._selected_thermostat_id) # type: ignore
                dev_reg = dr.async_get(self.hass)
                device = dev_reg.async_get_device(
                    identifiers={(DOMAIN, f"thermostat_{self._selected_thermostat_id}")}
                )
                if device:
                    dev_reg.async_remove_device(device.id)

                # 3. Aggiorna dati
                await self._coordinator.async_request_refresh()
                return await self.async_step_init()
            except Exception:
                _LOGGER.exception("Error deleting thermostat")
                return self.async_abort(reason="api_error")

        t_name = self._coordinator.data["thermostats"][self._selected_thermostat_id]["name"]
        return self.async_show_form(
            step_id="thermostat_remove",
            description_placeholders={"name": t_name},
            data_schema=vol.Schema({}),
        )


    # --- SENSOR MANAGEMENT FLOW ------------------------------------------------


    # --- STEP SENSOR THERMOSTAT SELECT -----------------------------------------

    async def async_step_sensor_thermostat_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Select the thermostat to manage sensors for."""
        thermostats = self._coordinator.data.get("thermostats", {})
        if not thermostats:
            return self.async_abort(reason="no_thermostats")

        options = {str(t_id): t_data["name"] for t_id, t_data in thermostats.items()}

        if user_input is not None:
            self._selected_thermostat_id = int(user_input["thermostat_id"])
            return await self.async_step_sensor_menu()

        return self.async_show_form(
            step_id="sensor_thermostat_select",
            data_schema=vol.Schema({vol.Required("thermostat_id"): vol.In(options)}),
        )


    # --- STEP SENSOR MENU ------------------------------------------------------

    async def async_step_sensor_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Choose action (Link or Unlink)."""
        options = {
            "link": "Link Sensor (Add/Update)",
            "unlink": "Unlink Sensor (Remove)",
        }

        if user_input is not None:
            if user_input["action"] == "link":
                return await self.async_step_sensor_type()
            else:
                return await self.async_step_sensor_unlink()

        t_name = self._coordinator.data["thermostats"][self._selected_thermostat_id]["name"]
        return self.async_show_form(
            step_id="sensor_menu",
            data_schema=vol.Schema({vol.Required("action"): vol.In(options)}),
            description_placeholders={"thermostat_name": t_name},
        )


    # --- STEP SENSOR TYPE ------------------------------------------------------

    async def async_step_sensor_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3A-1: Select the type of sensor slot."""
        if user_input is not None:
            self._selected_sensor_type_label = user_input["sensor_type"]
            return await self.async_step_sensor_entity()

        # Dropdown per il tipo di slot OASIS
        sensor_type_options = list(SENSOR_TYPES.keys())

        return self.async_show_form(
            step_id="sensor_type",
            data_schema=vol.Schema(
                {
                    vol.Required("sensor_type"): vol.In(sensor_type_options),
                }
            ),
        )


    # --- STEP SENSOR ENTITY ----------------------------------------------------

    async def async_step_sensor_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3A-2: Select the entity filtered by type and call API."""
        errors: dict[str, str] = {}
        
        # Recupera il backend type (es. "temp_in") dalla label scelta prima
        backend_type = SENSOR_TYPES[self._selected_sensor_type_label] # type: ignore
        
        # Determina device_class e dominio per il filtro
        device_class = SENSOR_DEVICE_CLASSES.get(backend_type)
        
        # Logica per dominio: Window/Door/Presence sono binary_sensor, il resto sensor
        domain_filter = "sensor"
        if backend_type in ["window", "door", "presence"]:
            domain_filter = "binary_sensor"

        if user_input is not None:
            entity_id = user_input["entity_id"]
            
            # Recupera il nome friendly dell'entità per passarlo al backend
            ent_reg = er.async_get(self.hass)
            entity_entry = ent_reg.async_get(entity_id)
            
            # Fallback sul nome se non trovato nel registry o nello stato
            friendly_name = entity_id
            if entity_entry and (entity_entry.name or entity_entry.original_name):
                friendly_name = entity_entry.name or entity_entry.original_name
            else:
                state = self.hass.states.get(entity_id)
                if state and state.name:
                    friendly_name = state.name

            try:
                # --- API CALL: LINK SENSOR ---
                await self._client.sensors.create(
                    thermostat_id=self._selected_thermostat_id, # type: ignore
                    entity_id=entity_id,
                    sensor_type=backend_type,
                    name=friendly_name
                )
                
                # Aggiorna coordinator per riflettere le modifiche
                # await self._coordinator.async_request_refresh()
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return await self.async_step_init()
                
            except Exception:
                _LOGGER.exception("Error linking sensor")
                errors["base"] = "api_error"

        # Configura il selettore con i filtri calcolati
        selector_config = selector.EntitySelectorConfig(
            domain=domain_filter,
            device_class=device_class,
            multiple=False
        )

        return self.async_show_form(
            step_id="sensor_entity",
            data_schema=vol.Schema(
                {
                    vol.Required("entity_id"): selector.EntitySelector(selector_config),
                }
            ),
            description_placeholders={
                "sensor_type": self._selected_sensor_type_label
            },
            errors=errors,
        )


    # --- STEP SENSOR UNLINK ----------------------------------------------------

    async def async_step_sensor_unlink(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3B: Unlink an existing sensor."""
        errors: dict[str, str] = {}
        
        # Recupera i sensori attuali per questo termostato
        t_data = self._coordinator.data["thermostats"][self._selected_thermostat_id]
        sensors_map = t_data.get("sensors_map", {})

        if not sensors_map:
            return self.async_abort(reason="no_sensors_to_remove")

        # Crea opzioni: "Nome Sensore (ID)"
        options = {
            str(s_id): f"{s_data['name']} ({s_data['type']})" 
            for s_id, s_data in sensors_map.items()
        }

        if user_input is not None:
            sensor_id = int(user_input["sensor_id"])
            try:
                # --- API CALL: UNLINK SENSOR ---
                await self._client.sensors.delete(sensor_id)
                ent_reg = er.async_get(self.hass)
                unique_id = f"oasis_sensor_{sensor_id}"
                
                # Cerchiamo l'entity_id nel dominio 'sensor' (o 'binary_sensor' per sicurezza)
                # La firma è: async_get_entity_id(domain, platform, unique_id)
                entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
                
                if not entity_id:
                    # Tentativo fallback se in futuro implementi binary_sensor
                    entity_id = ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
                
                if entity_id:
                    _LOGGER.debug("Removing unlinked entity from registry: %s", entity_id)
                    ent_reg.async_remove(entity_id)

                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                # await self._coordinator.async_request_refresh()
                return await self.async_step_init()
            except Exception:
                _LOGGER.exception("Error deleting sensor mapping")
                errors["base"] = "api_error"

        return self.async_show_form(
            step_id="sensor_unlink",
            data_schema=vol.Schema(
                {
                    vol.Required("sensor_id"): vol.In(options),
                }
            ),
            errors=errors
        )