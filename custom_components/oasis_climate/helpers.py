"""Helper functions for OASIS Climate."""
from __future__ import annotations
from typing import Any

from homeassistant.config_entries import ConfigEntry # type: ignore
from homeassistant.core import HomeAssistant # type: ignore

from .telemetry_manager import TelemetryManager

async def async_update_telemetry_config(
    hass: HomeAssistant,
    entry: ConfigEntry,
    manager: TelemetryManager,
    key: str,
    value: Any
) -> None:
    """
    DRY Helper: Updates TelemetryManager runtime settings AND persists them to ConfigEntry options.
    """
    # 1. Determina i nuovi valori basandosi sullo stato attuale del manager
    # Se la chiave corrisponde, usa il nuovo valore, altrimenti mantieni quello attuale
    new_enabled = value if key == "telemetry_enabled" else manager._enabled
    new_batch = int(value) if key == "telemetry_batch_size" else manager._batch_size
    new_interval = int(value) if key == "telemetry_flush_interval" else manager._flush_interval

    # 2. Aggiorna il Manager (Runtime - Effetto immediato)
    manager.update_settings(new_enabled, new_batch, new_interval)

    # 3. Salva su Disco (Persistenza)
    # Nota: Questo scatenerà un reload dell'integrazione a causa del listener in __init__.py
    new_options = {**entry.options, key: value}
    hass.config_entries.async_update_entry(entry, options=new_options)