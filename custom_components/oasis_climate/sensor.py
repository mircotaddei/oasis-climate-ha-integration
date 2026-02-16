"""Support for OASIS Climate sensors."""
from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.sensor import (SensorEntity, SensorDeviceClass, SensorStateClass, ) # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.const import UnitOfTemperature, PERCENTAGE # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity import DeviceInfo # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity # type: ignore
from homeassistant.exceptions import HomeAssistantError # type: ignore

from .const import DOMAIN, SENSOR_TYPES_REV, CONF_HOME_ID
from .coordinator import OasisUpdateCoordinator
from .api.base_api import OasisApiError

_LOGGER = logging.getLogger(__name__)


# Mappa per configurare le unità e le classi in base al tipo
SENSOR_CONFIG = {
    "temp_in": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "label": "Temperature (Indoor)"
    },
    "temp_out": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "label": "Temperature (Outdoor)"
    },
    "humidity_in": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "icon": "mdi:water-percent",
        "label": "Humidity (Indoor)"
    },
    "humidity_out": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "icon": "mdi:water-percent",
        "label": "Humidity (Outdoor)"
    },
    "luminosity": {
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "unit": "lx",
        "icon": "mdi:brightness-5",
        "label": "Luminosity"
    },
    # Default fallback
    "default": {
        "device_class": None,
        "unit": None,
        "icon": "mdi:eye",
        "label": "Sensor"
    }
}


# --- SETUP ENTRY -------------------------------------------------------------

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up OASIS sensors."""
    coordinator: OasisUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities = []
    thermostats = coordinator.data.get("thermostats", {})
    
    _LOGGER.debug("Setting up sensors. Found %d thermostats.", len(thermostats))

    for t_id, t_data in thermostats.items():
        sensors_map = t_data.get("sensors_map", {})
        _LOGGER.debug("Thermostat %s has %d sensors mapped.", t_id, len(sensors_map))
        
        for s_id, s_data in sensors_map.items():
            _LOGGER.debug("Creating sensor entity for: %s (Type: %s)", s_data.get("name"), s_data.get("type"))
            entities.append(OasisSensor(coordinator, t_id, s_id))
            entities.append(OasisLearningStatusSensor(coordinator, t_id))
            entities.append(OasisLearningProgressSensor(coordinator, t_id))
            entities.append(OasisModulationSensor(coordinator, t_id))
            entities.append(OasisScheduleSensor(coordinator, device_id=t_id, is_home=False))
            entities.append(OasisSimulatedTempSensor(coordinator, t_id))
            entities.append(OasisLastSeenSensor(coordinator, t_id))
            
    home_id = str(entry.data[CONF_HOME_ID])
    entities.append(OasisScheduleSensor(coordinator, device_id=home_id, is_home=True))
        
    async_add_entities(entities)


# --- OASIS SENSOR ------------------------------------------------------------

class OasisSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OASIS Sensor linked to a Thermostat."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: OasisUpdateCoordinator, thermostat_device_id: str, sensor_device_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._thermostat_id = thermostat_device_id
        self._sensor_id = sensor_device_id
        
        # Unique ID for the entity
        self._attr_unique_id = f"oasis_sensor_{self._sensor_id}"
        
        # Link this entity to the parent Thermostat Device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"thermostat_{self._thermostat_id}")},
        )
        
        # Set initial static attributes
        self._update_static_attributes()

    @property
    def _sensor_data(self) -> dict | None:
        """Helper to get the data for this specific sensor from the coordinator."""
        try:
            return self.coordinator.data["thermostats"][self._thermostat_id]["sensors_map"][self._sensor_id]
        except KeyError:
            return None

    def _update_static_attributes(self) -> None:
        """Update static attributes based on the sensor's type."""
        if not self._sensor_data:
            return

        sensor_type = self._sensor_data.get("type")
        config = SENSOR_CONFIG.get(sensor_type, {}) # type: ignore
        
        # The entity name will be the friendly name from the backend
        self._attr_name = self._sensor_data.get("name") or SENSOR_TYPES_REV.get(sensor_type, "Sensor") # type: ignore
        
        self._attr_device_class = config.get("device_class")
        self._attr_native_unit_of_measurement = config.get("unit")

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        if not self._sensor_data:
            return None

        # 1. Tentativo di lettura dal sensore locale mappato (Richiesta Utente)
        meta = self._sensor_data.get("meta", {})
        local_id = meta.get("local_id") or self._sensor_data.get("local_id")
        
        if local_id:
            local_state = self.hass.states.get(local_id)
            if local_state and local_state.state not in ("unknown", "unavailable"):
                # Restituiamo il valore locale per feedback immediato
                return local_state.state

        # 2. Fallback al valore cachato dal backend
        return self._sensor_data.get("cached_value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not self._sensor_data:
            return {}
            
        return {
            "cached_value": self._sensor_data.get("cached_value"),
            "last_reading_at": self._sensor_data.get("last_reading_at"),
            "oasis_type": self._sensor_data.get("type"),
            "weight": self._sensor_data.get("weight"),
            "is_active": self._sensor_data.get("is_active"),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # The entity is available if its data exists in the coordinator
        # and the coordinator is successfully updating.
        return self._sensor_data is not None and super().available


# --- OASIS LEARNING STATUS SENSOR --------------------------------------------

class OasisLearningStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Learning Status"
    _attr_icon = "mdi:brain"
    
    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_learning_status_{device_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def native_value(self):
        return self.coordinator.data["thermostats"].get(self._device_id, {}).get("learning_status")


# --- OASIS LEARNING PROGRESS SENSOR ------------------------------------------

class OasisLearningProgressSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Learning Progress"
    _attr_icon = "mdi:progress-check"
    _attr_native_unit_of_measurement = "%"
    
    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_learning_progress_{device_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def native_value(self):
        return self.coordinator.data["thermostats"].get(self._device_id, {}).get("learning_progress")


# --- OASIS MODULATION SENSOR -------------------------------------------------

class OasisModulationSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Boiler Modulation"
    _attr_icon = "mdi:fire"
    _attr_native_unit_of_measurement = "%"
    
    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_modulation_{device_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def native_value(self):
        val = self.coordinator.data["thermostats"].get(self._device_id, {}).get("current_modulation", 0.0)
        return round(val * 100, 1)


# --- OASIS HOME SCHEDULE SENSOR ----------------------------------------------

class OasisScheduleSensor(CoordinatorEntity, SensorEntity):
    """Sensor that renders the Schedule (Home or Thermostat) as an HTML Table."""
    _attr_has_entity_name = True
    _attr_name = "Active Schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, device_id: str, is_home: bool):
        super().__init__(coordinator)
        self._device_id = device_id
        self._is_home = is_home
        
        if is_home:
            self._attr_unique_id = f"oasis_home_schedule_{device_id}"
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"home_{device_id}")})
        else:
            self._attr_unique_id = f"oasis_thermostat_schedule_{device_id}"
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def _schedule_data(self) -> dict | None:
        """Retrieve schedule data based on entity type."""
        if self._is_home:
            return self.coordinator.data.get("home", {}).get("schedule")
        else:
            return self.coordinator.data.get("thermostats", {}).get(self._device_id, {}).get("schedule")

    @property
    def native_value(self):
        data = self._schedule_data
        if not data:
            return "Not Configured"
        return "Active (v{})".format(data.get("version", "?"))

    @property
    def extra_state_attributes(self):
        """Returns the formatted HTML table."""
        return {
            "html_table": self._generate_html_table(self._schedule_data),
            "raw_schedule": self._schedule_data
        }

    def _generate_html_table(self, data: dict | None) -> str:
        """Converts JSON schedule to HTML Table respecting preferences."""
        if not data:
            return "<i>No schedule data available.</i>"

        prefs = data.get("preferences", {"show_icon": True, "show_text": True, "show_temp": True})
        presets_map = {p["id"]: p for p in data.get("presets", [])}
        week_schedule = data.get("week_schedule", {})
        
        # Giorni ordinati
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        html = "<table style='width: 100%; border-collapse: collapse; font-size: 0.9em;'>"
        html += "<thead><tr><th style='text-align: left;'>Day</th><th style='text-align: left;'>Schedule</th></tr></thead><tbody>"

        for day in days:
            # Fallback a 'default' se il giorno specifico non è definito
            intervals = week_schedule.get(day) or week_schedule.get("default", [])
            
            day_label = day[:3].capitalize()
            html += f"<tr style='border-bottom: 1px solid var(--divider-color);'><td style='padding: 8px 4px; vertical-align: top;'><b>{day_label}</b></td><td style='padding: 8px 4px;'>"
            
            for interval in intervals:
                preset_id = interval.get("preset_id")
                preset = presets_map.get(preset_id, {})
                
                start = interval.get("start_time")
                end = interval.get("end_time")
                
                # Badge Style
                bg_color = self._map_tailwind_color(preset.get("color", "bg-gray-500"))
                badge_style = (
                    f"display: inline-block; background-color: {bg_color}; color: white; "
                    "padding: 2px 6px; border-radius: 4px; margin-bottom: 2px; margin-right: 4px; font-size: 0.85em;"
                )
                
                content = f"{start}-{end} "
                
                # Icon
                if prefs.get("show_icon") and preset.get("icon"):
                    icon_html = self._get_icon_html(preset["icon"])
                    content += f"{icon_html} "
                
                # Label
                if prefs.get("show_text"):
                    content += f"{preset.get('label', preset_id)} "
                
                # Temp
                if prefs.get("show_temp"):
                    temp = preset.get("temp_heat")
                    content += f"({temp}°)"

                html += f"<span style='{badge_style}'>{content}</span><br>"
            
            html += "</td></tr>"

        html += "</tbody></table>"
        return html

    def _get_icon_html(self, icon_name: str) -> str:
        """Translates simple icon name to HA icon tag."""
        # Mappa base per icone comuni, fallback a mdi:icon_name
        mdi_map = {
            "home": "mdi:home",
            "eco": "mdi:leaf",
            "bedtime": "mdi:bed",
            "flight": "mdi:airplane",
            "fire": "mdi:fire",
            "snowflake": "mdi:snowflake"
        }
        mdi_icon = mdi_map.get(icon_name, f"mdi:{icon_name}")
        return f"<ha-icon icon='{mdi_icon}' style='--mdc-icon-size: 14px; vertical-align: text-bottom;'></ha-icon>"

    def _map_tailwind_color(self, tailwind_class: str) -> str:
        """Maps Tailwind classes to Hex colors."""
        # Mappa semplificata per i colori usati nel default
        colors = {
            "bg-amber-400": "#fbbf24",
            "bg-emerald-400": "#34d399",
            "bg-indigo-500": "#6366f1",
            "bg-slate-500": "#64748b",
            "bg-red-500": "#ef4444",
            "bg-blue-500": "#3b82f6"
        }
        return colors.get(tailwind_class, "#888888") # Default grigio
    

# --- OASIS SIMULATED TEMP SENSOR ---------------------------------------------

class OasisSimulatedTempSensor(CoordinatorEntity, SensorEntity):
    """Digital Twin simulated temperature."""
    _attr_has_entity_name = True
    _attr_name = "Simulated Temperature (Digital Twin)"
    _attr_icon = "mdi:thermometer-auto"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_sim_temp_{device_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def native_value(self):
        return self.coordinator.data["thermostats"].get(self._device_id, {}).get("sim_internal_temp")


# --- OASIS LAST SEEN SENSOR --------------------------------------------------

class OasisLastSeenSensor(CoordinatorEntity, SensorEntity):
    """Timestamp of last contact."""
    _attr_has_entity_name = True
    _attr_name = "Last Seen"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, device_id):
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"oasis_last_seen_{device_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"thermostat_{device_id}")})

    @property
    def native_value(self):
        # TODO check if backend returns ISO 8601 string
        ts = self.coordinator.data["thermostats"].get(self._device_id, {}).get("last_seen_at")
        if ts:
            from datetime import datetime
            # Se è già datetime ok, altrimenti parse
            if isinstance(ts, str):
                return datetime.fromisoformat(ts)
            return ts
        return None