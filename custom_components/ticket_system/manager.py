"""Verwaltung und Persistenz der Tickets."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    ATTR_AUTHOR,
    ATTR_DESCRIPTION,
    ATTR_NOTIFY,
    ATTR_PRIORITY,
    ATTR_STATUS,
    ATTR_TITLE,
    DATA_MANAGER,
    DOMAIN,
    EVENT_TICKET_CREATED,
    EVENT_TICKET_DELETED,
    EVENT_TICKET_UPDATED,
    PRIORITIES,
    PRIORITY_LABELS,
    PRIORITY_MEDIUM,
    PRIORITY_ORDER,
    SIGNAL_TICKETS_UPDATED,
    STATUS_CLOSED,
    STATUS_LABELS,
    STATUS_OPEN,
    STATUSES,
    STORAGE_KEY,
    STORAGE_VERSION,
    TICKET_FIELDS,
)

_LOGGER = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 200


def _now() -> datetime:
    """Aktuelle Zeit in UTC."""
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    """Zeitstempel als ISO-8601-String (UTC, sekundengenau)."""
    return moment.isoformat(timespec="seconds")


class TicketManager:
    """Hält alle Tickets im Speicher und schreibt sie in den HA-Storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._tickets: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Laden / Speichern
    # ------------------------------------------------------------------
    async def async_load(self) -> None:
        """Lädt die Tickets aus dem Storage."""
        stored = await self._store.async_load() or {}
        raw_tickets = stored.get("tickets") or []

        tickets: dict[str, dict[str, Any]] = {}
        for raw in raw_tickets:
            if not isinstance(raw, dict):
                continue
            normalized = self._normalize(raw)
            if normalized is not None:
                tickets[normalized["id"]] = normalized

        self._tickets = tickets
        _LOGGER.debug("Ticketsystem: %s Ticket(s) geladen", len(self._tickets))

    async def _async_commit(self) -> None:
        """Schreibt den aktuellen Stand und informiert alle Zuhörer."""
        await self._store.async_save({"tickets": list(self._tickets.values())})
        async_dispatcher_send(self.hass, SIGNAL_TICKETS_UPDATED)

    # ------------------------------------------------------------------
    # Lesen
    # ------------------------------------------------------------------
    def async_list(
        self,
        status: str | None = None,
        priority: str | None = None,
    ) -> list[dict[str, Any]]:
        """Alle Tickets, absteigend nach Dringlichkeit, dann neueste zuerst."""
        result: list[dict[str, Any]] = []
        for ticket in self._tickets.values():
            if status is not None and ticket[ATTR_STATUS] != status:
                continue
            if priority is not None and ticket[ATTR_PRIORITY] != priority:
                continue
            result.append(dict(ticket))

        result.sort(
            key=lambda item: (
                PRIORITY_ORDER.get(item[ATTR_PRIORITY], 0),
                item["created_at"],
            ),
            reverse=True,
        )
        return result

    def async_get(self, ticket_id: str) -> dict[str, Any] | None:
        """Ein einzelnes Ticket (Kopie) oder None."""
        ticket = self._tickets.get(ticket_id)
        return dict(ticket) if ticket is not None else None

    def async_counts(self) -> dict[str, Any]:
        """Anzahl der Tickets nach Status und Dringlichkeit."""
        by_status = {status: 0 for status in STATUSES}
        by_priority = {priority: 0 for priority in PRIORITIES}
        for ticket in self._tickets.values():
            by_status[ticket[ATTR_STATUS]] = by_status.get(ticket[ATTR_STATUS], 0) + 1
            by_priority[ticket[ATTR_PRIORITY]] = (
                by_priority.get(ticket[ATTR_PRIORITY], 0) + 1
            )
        return {
            "total": len(self._tickets),
            "by_status": by_status,
            "by_priority": by_priority,
        }

    # ------------------------------------------------------------------
    # Schreiben
    # ------------------------------------------------------------------
    async def async_create(
        self,
        *,
        title: str,
        description: str = "",
        priority: str = PRIORITY_MEDIUM,
        status: str = STATUS_OPEN,
        author: str = "",
        notify: bool = True,
    ) -> dict[str, Any]:
        """Legt ein neues Ticket an."""
        async with self._lock:
            now = _now()
            ticket: dict[str, Any] = {
                "id": self._generate_id(now),
                ATTR_TITLE: _clean(title, MAX_TITLE_LENGTH) or "Ohne Titel",
                ATTR_DESCRIPTION: _clean(description, 10000),
                ATTR_PRIORITY: priority if priority in PRIORITIES else PRIORITY_MEDIUM,
                ATTR_STATUS: status if status in STATUSES else STATUS_OPEN,
                ATTR_AUTHOR: _clean(author, 100) or "Unbekannt",
                ATTR_NOTIFY: bool(notify),
                "created_at": _iso(now),
                "updated_at": _iso(now),
                "closed_at": _iso(now) if status == STATUS_CLOSED else None,
            }
            self._tickets[ticket["id"]] = ticket
            await self._async_commit()

        _LOGGER.debug(
            "Ticketsystem: Ticket %s erstellt (%s / %s)",
            ticket["id"],
            PRIORITY_LABELS.get(ticket[ATTR_PRIORITY], ticket[ATTR_PRIORITY]),
            STATUS_LABELS.get(ticket[ATTR_STATUS], ticket[ATTR_STATUS]),
        )
        self.hass.bus.async_fire(EVENT_TICKET_CREATED, {"ticket": dict(ticket)})
        return dict(ticket)

    async def async_update(
        self, ticket_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Aktualisiert Felder eines Tickets. Wirft KeyError, wenn unbekannt."""
        async with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise KeyError(ticket_id)

            before = dict(ticket)

            for field in TICKET_FIELDS:
                value = changes.get(field)
                if value is None:
                    continue
                if field == ATTR_TITLE:
                    ticket[field] = _clean(value, MAX_TITLE_LENGTH) or ticket[field]
                elif field == ATTR_DESCRIPTION:
                    ticket[field] = _clean(value, 10000)
                elif field == ATTR_AUTHOR:
                    ticket[field] = _clean(value, 100) or "Unbekannt"
                elif field == ATTR_PRIORITY and value in PRIORITIES:
                    ticket[field] = value
                elif field == ATTR_STATUS and value in STATUSES:
                    ticket[field] = value

            now = _now()
            ticket["updated_at"] = _iso(now)
            if ATTR_STATUS in changes:
                ticket["closed_at"] = (
                    _iso(now) if ticket[ATTR_STATUS] == STATUS_CLOSED else None
                )

            result = dict(ticket)
            changed = sorted(
                field
                for field in TICKET_FIELDS
                if before.get(field) != result.get(field)
            )
            await self._async_commit()

        self.hass.bus.async_fire(
            EVENT_TICKET_UPDATED, {"ticket": result, "changes": changed}
        )
        return result

    async def async_set_status(
        self, ticket_id: str, status: str
    ) -> dict[str, Any]:
        """Setzt ausschließlich den Status eines Tickets."""
        return await self.async_update(ticket_id, {ATTR_STATUS: status})

    async def async_delete(self, ticket_id: str) -> dict[str, Any]:
        """Löscht ein Ticket dauerhaft."""
        async with self._lock:
            ticket = self._tickets.pop(ticket_id, None)
            if ticket is None:
                raise KeyError(ticket_id)
            await self._async_commit()

        self.hass.bus.async_fire(EVENT_TICKET_DELETED, {"ticket": ticket})
        return ticket

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    @staticmethod
    def _generate_id(now: datetime) -> str:
        """Zeitstempel-basierte, eindeutige Ticket-ID."""
        return f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any] | None:
        """Bringt gespeicherte Tickets in eine gültige Form."""
        ticket_id = str(raw.get("id") or "").strip()
        if not ticket_id:
            return None

        priority = str(raw.get(ATTR_PRIORITY) or PRIORITY_MEDIUM).lower()
        if priority not in PRIORITIES:
            priority = PRIORITY_MEDIUM

        status = str(raw.get(ATTR_STATUS) or STATUS_OPEN).lower()
        if status not in STATUSES:
            status = STATUS_OPEN

        created_at = str(raw.get("created_at") or _iso(_now()))

        return {
            "id": ticket_id,
            ATTR_TITLE: str(raw.get(ATTR_TITLE) or "Ohne Titel"),
            ATTR_DESCRIPTION: str(raw.get(ATTR_DESCRIPTION) or ""),
            ATTR_PRIORITY: priority,
            ATTR_STATUS: status,
            ATTR_AUTHOR: str(raw.get(ATTR_AUTHOR) or "Unbekannt"),
            ATTR_NOTIFY: bool(raw.get(ATTR_NOTIFY, True)),
            "created_at": created_at,
            "updated_at": str(raw.get("updated_at") or created_at),
            "closed_at": raw.get("closed_at") or None,
        }


def _clean(value: Any, max_length: int) -> str:
    """Text säubern und auf eine maximale Länge begrenzen."""
    return str(value).strip()[:max_length]


def get_manager(hass: HomeAssistant) -> TicketManager | None:
    """Aktuell aktiven TicketManager zurückgeben (oder None)."""
    return hass.data.get(DOMAIN, {}).get(DATA_MANAGER)
