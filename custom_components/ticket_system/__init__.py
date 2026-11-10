"""Ticketsystem – ein leichtgewichtiges Ticketsystem für Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_FRONTEND_REGISTERED,
    DATA_MANAGER,
    DOMAIN,
    FRONTEND_DIR,
    FRONTEND_SCRIPT,
    FRONTEND_URL,
    PLATFORMS,
    VERSION,
)
from .manager import TicketManager
from .services import async_register_services, async_unregister_services
from .websocket_api import async_register_websocket_api

try:  # Home Assistant >= 2024.7
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # pragma: no cover - ältere Versionen
    StaticPathConfig = None  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """YAML-Setup – die Integration wird ausschließlich über die UI eingerichtet."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration einrichten."""
    manager = TicketManager(hass)
    await manager.async_load()

    hass.data.setdefault(DOMAIN, {})[DATA_MANAGER] = manager

    await _async_register_frontend(hass)
    async_register_websocket_api(hass)
    await async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Ticketsystem eingerichtet (%s)", entry.title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen (z. B. bei Neustart der Integration)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(DATA_MANAGER, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Integration wurde gelöscht – Services aufräumen."""
    await async_unregister_services(hass)
    hass.data.pop(DOMAIN, None)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Stellt die Karten-Datei unter /ticket_system/... bereit und lädt sie."""
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return

    script_path = FRONTEND_DIR / FRONTEND_SCRIPT
    if not script_path.is_file():
        _LOGGER.warning(
            "Ticketsystem: Frontend-Datei %s fehlt – die Karten stehen nicht zur Verfügung",
            script_path,
        )
        return

    try:
        if StaticPathConfig is not None and hasattr(
            hass.http, "async_register_static_paths"
        ):
            await hass.http.async_register_static_paths(
                [StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIR), False)]
            )
        else:  # pragma: no cover - ältere Versionen
            hass.http.register_static_path(
                FRONTEND_URL, str(FRONTEND_DIR), False
            )
    except RuntimeError:
        # Pfad wurde bereits registriert (z. B. nach einem Reload).
        _LOGGER.debug("Ticketsystem: statischer Pfad war bereits registriert")

    if "frontend" in hass.config.components:
        add_extra_js_url(
            hass, f"{FRONTEND_URL}/{FRONTEND_SCRIPT}?v={VERSION}"
        )
    else:  # pragma: no cover - ohne Frontend keine Karten
        _LOGGER.debug(
            "Ticketsystem: Frontend nicht geladen – Karten müssen manuell "
            "als Ressource %s/%s eingebunden werden",
            FRONTEND_URL,
            FRONTEND_SCRIPT,
        )

    hass.data[DATA_FRONTEND_REGISTERED] = True
