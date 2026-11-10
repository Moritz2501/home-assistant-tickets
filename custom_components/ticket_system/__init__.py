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
    DATA_NOTIFIER,
    DOMAIN,
    FRONTEND_DIR,
    FRONTEND_SCRIPT,
    FRONTEND_URL,
    PLATFORMS,
    VERSION,
)
from .manager import TicketManager
from .notifications import TicketNotifier
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

    notifier = TicketNotifier(hass, entry)
    notifier.async_start()

    data = hass.data.setdefault(DOMAIN, {})
    data[DATA_MANAGER] = manager
    data[DATA_NOTIFIER] = notifier

    await _async_register_frontend(hass)
    async_register_websocket_api(hass)
    await async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Änderungen an den Benachrichtigungs-Optionen sofort übernehmen.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    _LOGGER.debug("Ticketsystem eingerichtet (%s)", entry.title)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Optionen wurden geändert – Integration neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen (z. B. bei Neustart der Integration)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data.get(DOMAIN, {})
        notifier = data.pop(DATA_NOTIFIER, None)
        if notifier is not None:
            notifier.async_stop()
        data.pop(DATA_MANAGER, None)
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
