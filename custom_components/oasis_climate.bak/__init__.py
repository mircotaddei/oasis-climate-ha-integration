"""The OASIS Climate integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OasisApiClient, OasisApiConnectionError, OasisApiAuthError
from .const import DOMAIN, CONF_API_KEY, CONF_API_URL

_LOGGER = logging.getLogger(__name__)

# Elenco delle piattaforme da caricare. 
# Per ora partiamo con i sensori (per visualizzare stato e advice).
# In futuro aggiungeremo Platform.CLIMATE o Platform.SWITCH per il controllo.
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OASIS Climate from a config entry."""
    
    # 1. Recupera i dati di configurazione
    api_key = entry.data[CONF_API_KEY]
    api_url = entry.data[CONF_API_URL]

    # 2. Inizializza il Client API
    # Usiamo la sessione aiohttp condivisa di Home Assistant per efficienza
    session = async_get_clientsession(hass)
    client = OasisApiClient(session=session, api_key=api_key, api_url=api_url)

    # 3. Verifica Connessione Iniziale
    # Se l'API non risponde all'avvio, lanciamo ConfigEntryNotReady
    # così HA riproverà automaticamente in background.
    try:
        valid = await client.async_validate_api_key()
        if not valid:
            _LOGGER.error("Invalid API Key provided during setup")
            return False
    except OasisApiConnectionError as exception:
        raise ConfigEntryNotReady(f"Error connecting to OASIS Cloud: {exception}") from exception

    # 4. Salva il client nel contesto globale di HA
    # Questo permette a sensor.py di recuperare 'client' tramite entry.entry_id
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    # 5. Carica le piattaforme (es. sensor.py)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Scarica le piattaforme
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Rimuove i dati dalla memoria
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok