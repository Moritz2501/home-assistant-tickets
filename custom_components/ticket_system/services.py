"""Service-Handler der Ticketsystem-Integration."""

from __future__ import annotations

import logging
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_AUTHOR,
    ATTR_DESCRIPTION,
    ATTR_KIND,
    ATTR_MESSAGE,
    ATTR_NOTIFY,
    ATTR_NOTIFY_SERVICE,
    ATTR_PRIORITY,
    ATTR_STATUS,
    ATTR_TARGET,
    ATTR_TICKET_ID,
    ATTR_TITLE,
    DOMAIN,
    NOTIFY_KIND_INFO,
    NOTIFY_KINDS,
    NOTIFY_TARGET_ADMINS,
    NOTIFY_TARGETS,
    PRIORITIES,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    SERVICE_CREATE,
    SERVICE_DELETE,
    SERVICE_NOTIFY,
    SERVICE_SET_STATUS,
    SERVICE_UPDATE,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
    STATUSES,
)
from .manager import TicketManager, get_manager
from .notifications import TicketNotifier, get_notifier

_LOGGER = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 200

# ---------------------------------------------------------------------------
# Eingabe-Normalisierung (englische UND deutsche Werte erlaubt)
# ---------------------------------------------------------------------------
_PRIORITY_ALIASES: Final[dict[str, str]] = {
    "low": PRIORITY_LOW,
    "niedrig": PRIORITY_LOW,
    "gering": PRIORITY_LOW,
    "1": PRIORITY_LOW,
    "medium": PRIORITY_MEDIUM,
    "mittel": PRIORITY_MEDIUM,
    "normal": PRIORITY_MEDIUM,
    "2": PRIORITY_MEDIUM,
    "high": PRIORITY_HIGH,
    "hoch": PRIORITY_HIGH,
    "3": PRIORITY_HIGH,
    "critical": PRIORITY_CRITICAL,
    "kritisch": PRIORITY_CRITICAL,
    "dringend": PRIORITY_CRITICAL,
    "4": PRIORITY_CRITICAL,
}

_STATUS_ALIASES: Final[dict[str, str]] = {
    "open": STATUS_OPEN,
    "offen": STATUS_OPEN,
    "neu": STATUS_OPEN,
    "1": STATUS_OPEN,
    "in_progress": STATUS_IN_PROGRESS,
    "in progress": STATUS_IN_PROGRESS,
    "in bearbeitung": STATUS_IN_PROGRESS,
    "bearbeitung": STATUS_IN_PROGRESS,
    "progress": STATUS_IN_PROGRESS,
    "2": STATUS_IN_PROGRESS,
    "closed": STATUS_CLOSED,
    "abgeschlossen": STATUS_CLOSED,
    "geschlossen": STATUS_CLOSED,
    "erledigt": STATUS_CLOSED,
    "done": STATUS_CLOSED,
    "3": STATUS_CLOSED,
}


def _as_priority(value: Any) -> str:
    """Wandelt beliebige Dringlichkeits-Schreibweisen in den Schlüssel um."""
    key = _PRIORITY_ALIASES.get(str(value).strip().lower())
    if key is None:
        raise vol.Invalid(
            f"Unbekannte Dringlichkeit '{value}'. Erlaubt: {', '.join(PRIORITIES)} "
            "oder Niedrig/Mittel/Hoch/Kritisch."
        )
    return key


def _as_status(value: Any) -> str:
    """Wandelt beliebige Status-Schreibweisen in den Schlüssel um."""
    key = _STATUS_ALIASES.get(str(value).strip().lower())
    if key is None:
        raise vol.Invalid(
            f"Unbekannter Status '{value}'. Erlaubt: {', '.join(STATUSES)} "
            "oder Offen/In Bearbeitung/Abgeschlossen."
        )
    return key


_CREATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TITLE): vol.All(
            cv.string, vol.Length(min=1, max=MAX_TITLE_LENGTH)
        ),
        vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
        vol.Optional(ATTR_PRIORITY, default=PRIORITY_MEDIUM): vol.All(
            cv.string, _as_priority
        ),
        vol.Optional(ATTR_STATUS, default=STATUS_OPEN): vol.All(
            cv.string, _as_status
        ),
        vol.Optional(ATTR_AUTHOR, default=""): cv.string,
        vol.Optional(ATTR_NOTIFY, default=True): cv.boolean,
    }
)

_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TICKET_ID): cv.string,
        vol.Optional(ATTR_TITLE): vol.All(
            cv.string, vol.Length(min=1, max=MAX_TITLE_LENGTH)
        ),
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Optional(ATTR_PRIORITY): vol.All(cv.string, _as_priority),
        vol.Optional(ATTR_STATUS): vol.All(cv.string, _as_status),
        vol.Optional(ATTR_AUTHOR): cv.string,
    }
)

_SET_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TICKET_ID): cv.string,
        vol.Required(ATTR_STATUS): vol.All(cv.string, _as_status),
    }
)

_DELETE_SCHEMA = vol.Schema({vol.Required(ATTR_TICKET_ID): cv.string})

_NOTIFY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TICKET_ID): cv.string,
        vol.Optional(ATTR_KIND, default=NOTIFY_KIND_INFO): vol.In(NOTIFY_KINDS),
        vol.Optional(ATTR_TARGET, default=NOTIFY_TARGET_ADMINS): vol.In(
            NOTIFY_TARGETS
        ),
        vol.Optional(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_NOTIFY_SERVICE): cv.string,
    }
)


def _require_manager(hass: HomeAssistant) -> TicketManager:
    """Manager holen oder einen verständlichen Fehler werfen."""
    manager = get_manager(hass)
    if manager is None:
        raise HomeAssistantError(
            "Das Ticketsystem ist nicht eingerichtet. "
            "Bitte die Integration unter Einstellungen > Geräte & Dienste hinzufügen."
        )
    return manager


def _require_notifier(hass: HomeAssistant) -> TicketNotifier:
    """Notifier holen oder einen verständlichen Fehler werfen."""
    notifier = get_notifier(hass)
    if notifier is None:
        raise HomeAssistantError(
            "Die Benachrichtigungen des Ticketsystems sind nicht verfügbar. "
            "Bitte die Integration neu laden."
        )
    return notifier


async def async_register_services(hass: HomeAssistant) -> None:
    """Registriert alle Ticket-Services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_CREATE):
        return

    async def async_handle_create(call: ServiceCall) -> ServiceResponse:
        manager = _require_manager(hass)
        ticket = await manager.async_create(
            title=call.data[ATTR_TITLE],
            description=call.data.get(ATTR_DESCRIPTION, ""),
            priority=call.data.get(ATTR_PRIORITY, PRIORITY_MEDIUM),
            status=call.data.get(ATTR_STATUS, STATUS_OPEN),
            author=call.data.get(ATTR_AUTHOR, ""),
            notify=call.data.get(ATTR_NOTIFY, True),
        )
        return {"ticket_id": ticket["id"], "ticket": ticket}

    async def async_handle_update(call: ServiceCall) -> ServiceResponse:
        manager = _require_manager(hass)
        ticket_id = call.data[ATTR_TICKET_ID]
        changes = {
            key: call.data[key]
            for key in (ATTR_TITLE, ATTR_DESCRIPTION, ATTR_PRIORITY, ATTR_STATUS, ATTR_AUTHOR)
            if key in call.data
        }
        try:
            ticket = await manager.async_update(ticket_id, changes)
        except KeyError as err:
            raise ServiceValidationError(
                f"Ticket '{ticket_id}' wurde nicht gefunden."
            ) from err
        return {"ticket": ticket}

    async def async_handle_set_status(call: ServiceCall) -> ServiceResponse:
        manager = _require_manager(hass)
        ticket_id = call.data[ATTR_TICKET_ID]
        try:
            ticket = await manager.async_set_status(
                ticket_id, call.data[ATTR_STATUS]
            )
        except KeyError as err:
            raise ServiceValidationError(
                f"Ticket '{ticket_id}' wurde nicht gefunden."
            ) from err
        return {"ticket": ticket}

    async def async_handle_delete(call: ServiceCall) -> ServiceResponse:
        manager = _require_manager(hass)
        ticket_id = call.data[ATTR_TICKET_ID]
        try:
            ticket = await manager.async_delete(ticket_id)
        except KeyError as err:
            raise ServiceValidationError(
                f"Ticket '{ticket_id}' wurde nicht gefunden."
            ) from err
        return {"ticket_id": ticket_id, "deleted": True, "ticket": ticket}

    async def async_handle_notify(call: ServiceCall) -> ServiceResponse:
        notifier = _require_notifier(hass)
        manager = _require_manager(hass)
        ticket_id = call.data[ATTR_TICKET_ID]
        ticket = manager.async_get(ticket_id)
        if ticket is None:
            raise ServiceValidationError(
                f"Ticket '{ticket_id}' wurde nicht gefunden."
            )

        result = await notifier.async_notify_ticket(
            ticket,
            kind=call.data.get(ATTR_KIND, NOTIFY_KIND_INFO),
            target=call.data.get(ATTR_TARGET, NOTIFY_TARGET_ADMINS),
            message=call.data.get(ATTR_MESSAGE),
            title=call.data.get(ATTR_TITLE),
            service=call.data.get(ATTR_NOTIFY_SERVICE),
        )

        if not result["sent"]:
            raise HomeAssistantError(
                "Es konnte keine Benachrichtigung gesendet werden. Bitte in den "
                "Optionen der Integration mindestens einen vorhandenen "
                "Benachrichtigungsdienst auswählen."
            )

        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE,
        async_handle_create,
        schema=_CREATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE,
        async_handle_update,
        schema=_UPDATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_STATUS,
        async_handle_set_status,
        schema=_SET_STATUS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE,
        async_handle_delete,
        schema=_DELETE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NOTIFY,
        async_handle_notify,
        schema=_NOTIFY_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    _LOGGER.debug("Ticketsystem: Services registriert")


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Entfernt alle Ticket-Services (beim Löschen der Integration)."""
    for service in (
        SERVICE_CREATE,
        SERVICE_UPDATE,
        SERVICE_SET_STATUS,
        SERVICE_DELETE,
        SERVICE_NOTIFY,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
