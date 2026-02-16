"""Telemetry Manager for OASIS Climate."""
from __future__ import annotations

import logging
import asyncio
from typing import Any, Callable

from homeassistant.core import HomeAssistant, Event, callback  # type: ignore
from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.helpers.event import async_track_state_change_event  # type: ignore
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN  # type: ignore

_LOGGER = logging.getLogger(__name__)


# --- TELEMETRY MANAGER --------------------------------------------------------

class TelemetryManager:
    """Handles data collection, buffering and batch sending to OASIS."""

    def __init__(self, hass: HomeAssistant, client: Any, coordinator: Any, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.client = client
        self.coordinator = coordinator
        self.entry = entry
        
        # Default settings (will be updated by Switch/Number entities)
        self._enabled = self.entry.options.get("telemetry_enabled", True)
        self._batch_size = self.entry.options.get("telemetry_batch_size", 20)
        self._flush_interval = self.entry.options.get("telemetry_flush_interval", 300)
        
        self._buffer: list[dict[str, Any]] = []
        self._listeners: list[Callable] = []
        self._flush_task: asyncio.Task | None = None


    # --- UPDATE SETTINGS ------------------------------------------------------

    def update_settings(self, enabled: bool, batch_size: int, interval: int) -> None:
        """Update telemetry settings dynamically."""
        self._enabled = enabled
        self._batch_size = batch_size
        self._flush_interval = interval
        _LOGGER.debug("Telemetry settings updated: Enabled=%s, Batch=%d, Interval=%d", enabled, batch_size, interval)


    # --- START ----------------------------------------------------------------

    async def async_start(self) -> None:
        """Start listening to state changes for mapped sensors."""
        # Ensure clean state
        self.async_stop() 
        
        # Small delay to allow HA to finish startup if called during setup
        await asyncio.sleep(1)

        thermostats = self.coordinator.data.get("thermostats", {})
        _LOGGER.debug("Telemetry Manager starting. Found %d thermostats.", len(thermostats))

        for t_device_id, t_data in thermostats.items():
            sensors_map = t_data.get("sensors_map", {})
            
            for s_device_id, s_data in sensors_map.items():
                # 1. Identifica l'entità HA sorgente (local_id)
                # Cerca prima in 'meta' (nuovo standard), poi fallback al top level
                meta = s_data.get("meta") or {}
                ha_entity_id = meta.get("local_id") or s_data.get("local_id")

                if not ha_entity_id:
                    # Questo sensore non è mappato su HA (es. sensore fisico diretto)
                    continue

                # 2. Verifica esistenza (solo per debug, il listener funziona anche se l'entità appare dopo)
                if not self.hass.states.get(ha_entity_id):
                    _LOGGER.debug("Mapped entity %s not currently found in HA, waiting for it.", ha_entity_id)
                else:
                    _LOGGER.debug("Mapping Telemetry: HA '%s' -> OASIS '%s'", ha_entity_id, s_device_id)
                
                # 3. Avvia il listener
                # Passiamo t_device_id (per il flush) e s_device_id (per il payload)
                remove_listener = async_track_state_change_event(
                    self.hass, 
                    [ha_entity_id], 
                    self._create_on_state_change_callback(t_device_id, s_device_id)
                )
                self._listeners.append(remove_listener)

        # Start the periodic flush timer
        if not self._flush_task:
            self._flush_task = self.hass.async_create_task(self._periodic_flush_loop())


    # --- STOP -----------------------------------------------------------------

    def async_stop(self) -> None:
        """Stop all listeners and timers."""
        _LOGGER.debug("Stopping Telemetry Manager...")
        
        # 1. Remove state listeners
        while self._listeners:
            self._listeners.pop()()
            
        # 2. Cancel background task
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
            _LOGGER.debug("Periodic flush task cancelled.")


    # --- CREATE ON STATE CHANGE CALLBACK --------------------------------------

    def _create_on_state_change_callback(self, thermostat_device_id: str, sensor_device_id: str):
        """Create a callback that captures the specific device context."""
        
        @callback
        async def _on_state_change(event: Event) -> None:
            if not self._enabled:
                return

            new_state = event.data.get("new_state")
            
            # Ignore unavailable/unknown states to keep backend data clean
            if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return

            # Normalize value to float
            try:
                if new_state.state == STATE_ON:
                    value = 1.0
                elif new_state.state == STATE_OFF:
                    value = 0.0
                else:
                    value = float(new_state.state)
            except (ValueError, TypeError):
                # Non-numeric state (and not on/off), skip
                return

            # Add to buffer
            reading = {
                "device_id": sensor_device_id, # Backend expects the sensor's device_id here
                "value": value,
                "timestamp": new_state.last_changed.isoformat()
            }
            
            self._buffer.append(reading)
            
            # Check batch size
            if len(self._buffer) >= self._batch_size:
                # Trigger flush non-blockingly
                self.hass.async_create_task(self.async_flush(thermostat_device_id))

        return _on_state_change


    # --- PERIODIC FLUSH LOOP ---------------------------------------------------

    async def _periodic_flush_loop(self) -> None:
        """Periodically flush the buffer even if not full."""
        try:
            while True:
                await asyncio.sleep(self._flush_interval)
                if self._buffer:
                    await self.async_flush_all()
        except asyncio.CancelledError:
            # Task cancelled during shutdown
            pass


    # --- FLUSH ALL ------------------------------------------------------------

    async def async_flush_all(self) -> None:
        """Flush buffer using the first available thermostat ID (simplification)."""
        if not self._buffer:
            return
            
        thermostats = self.coordinator.data.get("thermostats", {})
        if not thermostats:
            return
            
        # In a multi-thermostat setup, ideally we group readings by thermostat.
        # For now, we assume sensors belong to the home structure and use the first thermostat
        # as the gateway for the API call.
        first_t_dev_id = list(thermostats.keys())[0]
        await self.async_flush(first_t_dev_id)


    # --- FLUSH ----------------------------------------------------------------

    async def async_flush(self, device_id: str) -> None:
        """Send the current buffer to the backend."""
        if not self._buffer:
            return

        # Copy and clear buffer immediately to avoid race conditions
        readings_to_send = list(self._buffer)
        self._buffer.clear()

        _LOGGER.debug("Flushing telemetry batch (%d items) for device %s", len(readings_to_send), device_id)

        # Send via API
        success = await self.client.async_send_telemetry(device_id, readings_to_send)
        
        if not success:
            _LOGGER.warning("Failed to send telemetry batch. Data lost.")
            # Future improvement: Implement retry buffer with limits