"""Constants for the OASIS Climate integration."""

DOMAIN = "oasis_climate"

# Configuration Keys
CONF_API_URL = "api_url"
CONF_API_KEY = "api_key"
CONF_HOME_ID = "home_id"


# Options Flow Keys
CONF_CREATE_NEW_HOME = "create_new_home"
CONF_NEW_HOME_NAME = "new_home_name"


# Defaults
DEFAULT_API_URL = "http://host.docker.internal:8000/api/v1"
# DEFAULT_API_URL = "https://oasis-climate.com/api/v1"


# --- SENSOR TYPES -------------------------------------------------------------

# Mapping: Label -> Backend Enum Value
SENSOR_TYPES = {
    "Temperature (Indoor)": "temp_in",
    "Temperature (Outdoor)": "temp_out",
    "Humidity (Indoor)": "humidity_in",
    "Humidity (Outdoor)": "humidity_out",
    "Luminosity": "luminosity",
    "Rain": "rain",
    "Presence": "presence",
    "Window Contact": "window",
    "Door Contact": "door",
    "Power (Watts)": "power",
    "Energy (kWh)": "energy",
    "CO2": "co2",
    "Relay State (Boiler ON/OFF)": "relay_state",
    "OpenTherm Modulation": "opentherm_modulation",
    "PWM Level": "pwm_level",
    "Water Temp (Supply)": "water_temp_supply",
    "Water Temp (Return)": "water_temp_return",
    "Boiler Error Code": "boiler_error_code",
    "Battery Level": "battery_level",
    "Signal Strength": "signal_strength"
}

# Reverse mapping for UI display
SENSOR_TYPES_REV = {v: k for k, v in SENSOR_TYPES.items()}


# --- SENSOR DEVICE CLASSES ----------------------------------------------------

SENSOR_DEVICE_CLASSES = {
    "temp_in": "temperature",
    "temp_out": "temperature",
    "humidity_in": "humidity",
    "humidity_out": "humidity",
    "luminosity": "illuminance",
    "power": "power",
    "energy": "energy",
    "co2": "carbon_dioxide",
    "battery_level": "battery",
    "window": "window", 
    "door": "door",     
    "presence": "occupancy",
    "water_temp_supply": "temperature",
    "water_temp_return": "temperature",
    "signal_strength": "signal_strength",
    "relay_state": None,
    "opentherm_modulation": None,
    "pwm_level": None,
    "boiler_error_code": None
}


# Sensor Mappings
CONF_SENSOR_MAPPINGS = "sensor_mappings" # Dict[oasis_device_id, ha_entity_id]

# Telemetry Configuration Keys
CONF_TELEMETRY_ENABLED = "telemetry_enabled"
CONF_TELEMETRY_BATCH_SIZE = "telemetry_batch_size"
CONF_TELEMETRY_FLUSH_INTERVAL = "telemetry_flush_interval"

# Telemetry Defaults
DEFAULT_TELEMETRY_ENABLED = True
DEFAULT_TELEMETRY_BATCH_SIZE = 20
DEFAULT_TELEMETRY_FLUSH_INTERVAL = 300  # 5 minutes in seconds