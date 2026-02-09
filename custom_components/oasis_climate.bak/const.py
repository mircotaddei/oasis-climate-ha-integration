"""Constants for the OASIS Climate integration."""

DOMAIN = "oasis_climate"

# --- Configuration Keys (used in config_flow and entry.data) ---
CONF_API_KEY = "api_key"
CONF_API_URL = "api_url"
CONF_HOME_ID = "home_id"
CONF_HOME_NAME = "home_name"

# --- API Defaults ---
# Questo è solo un valore di default da mostrare nel form, non una chiave di configurazione
DEFAULT_API_URL = "http://host.docker.internal:8000/api/v1" 

# --- Entity Configuration Keys (used in options_flow) ---
CONF_THERMOSTAT_ID = "thermostat_id"
CONF_SENSOR_TEMP_IN = "sensor_temp_in"
CONF_SENSOR_TEMP_OUT = "sensor_temp_out"
CONF_SENSOR_HUMIDITY = "sensor_humidity"
CONF_SWITCH_BOILER = "switch_boiler"

# --- Service Attributes ---
ATTR_ADVICE_ID = "advice_id"
ATTR_RESPONSE = "response"
SERVICE_SUBMIT_FEEDBACK = "submit_feedback"