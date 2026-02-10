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
# DEFAULT_API_URL = "http://host.docker.internal:8000/api/v1"
DEFAULT_API_URL = "https://oasis-climate.com/api/v1"

# --- SENSOR TYPES ---
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
    "CO2": "co2"
}

# Reverse mapping for UI display
SENSOR_TYPES_REV = {v: k for k, v in SENSOR_TYPES.items()}

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
    "window": "window", # Binary Sensor
    "door": "door",     # Binary Sensor
    "presence": "occupancy" # Binary Sensor
}