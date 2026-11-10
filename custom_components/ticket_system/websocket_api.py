"""WebSocket-API für die Lovelace-Karten.

Die Karten lesen Tickets über eine authentifizierte WebSocket-Verbindung
(`ticket_system/list` und `ticket_system/subscribe`). Schreibende Zugriffe
laufen über die normalen Home-Assistant-Services und damit über die
Benutzerberechtigungen von Home Assistant.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    PRIORITIES,
    SIGNAL_TICKETS_UPDATED,
    STATUSES,
)
from .manager import TicketManager, get_manager

_LOGGER = logging.getLogger(__name__)

WS_TYPE_LIST = f"{DOMAIN}/list"
WS_TYPE_SUBSCRIBE = f"{DOMAIN}/subscribe"


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Registriert die WebSocket-Befehle (idempotent)."""
    websocket_api.async_register_command(hass, ws_list_tickets)
    websocket_api.async_register_command(hass, ws_subscribe_tickets)


def _get_manager(hass: HomeAssistant, connection, msg) -> TicketManager | None:
    """Manager holen, sonst einen WS-Fehler senden."""
    manager = get_manager(hass)
    if manager is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Das Ticketsystem ist nicht eingerichtet.",
        )
        return None
    return manager


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LIST,
        vol.Optional("status"): vol.In(STATUSES),
        vol.Optional("priority"): vol.In(PRIORITIES),
    }
)
@websocket_api.async_response
async def ws_list_tickets(
    hass: HomeAssistant, connection, msg
) -> None:
    """Liefert alle Tickets."""
    manager = _get_manager(hass, connection, msg)
    if manager is None:
        return

    connection.send_result(
        msg["id"],
        {
            "tickets": manager.async_list(
                status=msg.get("status"),
                priority=msg.get("priority"),
            )
        },
    )


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_SUBSCRIBE})
@callback
def ws_subscribe_tickets(hass: HomeAssistant, connection, msg) -> None:
    """Abonniert Änderungen an der Ticketliste (Push bei jeder Änderung)."""
    manager = _get_manager(hass, connection, msg)
    if manager is None:
        return

    @callback
    def _forward() -> None:
        connection.send_message(
            websocket_api.event_message(
                msg["id"], {"tickets": manager.async_list()}
            )
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_TICKETS_UPDATED, _forward
    )
    connection.send_result(msg["id"])
    _forward()
