"""Konstanten für die Ticketsystem-Integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

DOMAIN: Final = "ticket_system"
NAME: Final = "Ticketsystem"
VERSION: Final = "1.1.6"

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
CONF_NAME: Final = "name"
DEFAULT_NAME: Final = "Ticketsystem"

# ---------------------------------------------------------------------------
# Speicherung
# ---------------------------------------------------------------------------
STORAGE_KEY: Final = f"{DOMAIN}.tickets"
STORAGE_VERSION: Final = 1

PLATFORMS: Final = ["sensor"]

# Interne Signale / Daten-Keys
SIGNAL_TICKETS_UPDATED: Final = f"{DOMAIN}_tickets_updated"
DATA_MANAGER: Final = "manager"
DATA_NOTIFIER: Final = "notifier"
DATA_FRONTEND_REGISTERED: Final = f"{DOMAIN}_frontend_registered"

# ---------------------------------------------------------------------------
# Dringlichkeit
# ---------------------------------------------------------------------------
PRIORITY_LOW: Final = "low"
PRIORITY_MEDIUM: Final = "medium"
PRIORITY_HIGH: Final = "high"
PRIORITY_CRITICAL: Final = "critical"

PRIORITIES: Final = (
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_HIGH,
    PRIORITY_CRITICAL,
)

PRIORITY_ORDER: Final = {
    PRIORITY_LOW: 1,
    PRIORITY_MEDIUM: 2,
    PRIORITY_HIGH: 3,
    PRIORITY_CRITICAL: 4,
}

PRIORITY_LABELS: Final = {
    PRIORITY_LOW: "Niedrig",
    PRIORITY_MEDIUM: "Mittel",
    PRIORITY_HIGH: "Hoch",
    PRIORITY_CRITICAL: "Kritisch",
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
STATUS_OPEN: Final = "open"
STATUS_IN_PROGRESS: Final = "in_progress"
STATUS_CLOSED: Final = "closed"

STATUSES: Final = (
    STATUS_OPEN,
    STATUS_IN_PROGRESS,
    STATUS_CLOSED,
)

STATUS_ORDER: Final = {
    STATUS_OPEN: 1,
    STATUS_IN_PROGRESS: 2,
    STATUS_CLOSED: 3,
}

STATUS_LABELS: Final = {
    STATUS_OPEN: "Offen",
    STATUS_IN_PROGRESS: "In Bearbeitung",
    STATUS_CLOSED: "Abgeschlossen",
}

# ---------------------------------------------------------------------------
# Ticket-Attribute
# ---------------------------------------------------------------------------
ATTR_TICKET_ID: Final = "ticket_id"
ATTR_TITLE: Final = "title"
ATTR_DESCRIPTION: Final = "description"
ATTR_PRIORITY: Final = "priority"
ATTR_STATUS: Final = "status"
ATTR_AUTHOR: Final = "author"
ATTR_CREATED_AT: Final = "created_at"
ATTR_UPDATED_AT: Final = "updated_at"
ATTR_CLOSED_AT: Final = "closed_at"

TICKET_FIELDS: Final = (
    ATTR_TITLE,
    ATTR_DESCRIPTION,
    ATTR_PRIORITY,
    ATTR_STATUS,
    ATTR_AUTHOR,
)

# ---------------------------------------------------------------------------
# Services und Events
# ---------------------------------------------------------------------------
SERVICE_CREATE: Final = "create"
SERVICE_UPDATE: Final = "update"
SERVICE_SET_STATUS: Final = "set_status"
SERVICE_DELETE: Final = "delete"
SERVICE_NOTIFY: Final = "notify"

SERVICES: Final = (
    SERVICE_CREATE,
    SERVICE_UPDATE,
    SERVICE_SET_STATUS,
    SERVICE_DELETE,
    SERVICE_NOTIFY,
)

EVENT_TICKET_CREATED: Final = f"{DOMAIN}_ticket_created"
EVENT_TICKET_UPDATED: Final = f"{DOMAIN}_ticket_updated"
EVENT_TICKET_DELETED: Final = f"{DOMAIN}_ticket_deleted"

# ---------------------------------------------------------------------------
# Benachrichtigungen
# ---------------------------------------------------------------------------
CONF_NOTIFY_SERVICES: Final = "notify_services"
CONF_CREATOR_NOTIFY_SERVICES: Final = "creator_notify_services"
CONF_NOTIFY_ON_CREATE: Final = "notify_on_create"
CONF_NOTIFY_ON_CLOSE: Final = "notify_on_close"
CONF_NOTIFY_CRITICAL_TTS: Final = "notify_critical_tts"
CONF_TTS_ENTITY: Final = "tts_entity"
CONF_TTS_MEDIA_PLAYERS: Final = "tts_media_players"
CONF_TTS_MESSAGE: Final = "tts_message"

DEFAULT_NOTIFY_SERVICES: Final = ["notify.persistent_notification"]
DEFAULT_TTS_MESSAGE: Final = (
    "Kritisches Ticket im Ticketsystem: {title}. Bitte sofort prüfen."
)

DEFAULT_OPTIONS: Final[dict[str, Any]] = {
    CONF_NOTIFY_SERVICES: DEFAULT_NOTIFY_SERVICES,
    CONF_CREATOR_NOTIFY_SERVICES: [],
    CONF_NOTIFY_ON_CREATE: True,
    CONF_NOTIFY_ON_CLOSE: True,
    CONF_NOTIFY_CRITICAL_TTS: True,
    CONF_TTS_ENTITY: None,
    CONF_TTS_MEDIA_PLAYERS: [],
    CONF_TTS_MESSAGE: DEFAULT_TTS_MESSAGE,
}

ATTR_NOTIFY: Final = "notify"
ATTR_KIND: Final = "kind"
ATTR_TARGET: Final = "target"
ATTR_MESSAGE: Final = "message"
ATTR_NOTIFY_SERVICE: Final = "notify_service"

NOTIFY_KIND_INFO: Final = "info"
NOTIFY_KIND_REMINDER: Final = "reminder"
NOTIFY_KINDS: Final = (NOTIFY_KIND_INFO, NOTIFY_KIND_REMINDER)

NOTIFY_TARGET_ADMINS: Final = "admins"
NOTIFY_TARGET_CREATOR: Final = "creator"
NOTIFY_TARGET_ALL: Final = "all"
NOTIFY_TARGETS: Final = (
    NOTIFY_TARGET_ADMINS,
    NOTIFY_TARGET_CREATOR,
    NOTIFY_TARGET_ALL,
)

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
FRONTEND_URL: Final = f"/{DOMAIN}"
FRONTEND_SCRIPT: Final = "ticket-system-cards.js"
FRONTEND_DIR: Final = Path(__file__).parent / "frontend"
