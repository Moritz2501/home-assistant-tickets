"""Benachrichtigungen zu Ticket-Ereignissen.

Die Logik hängt an den Bus-Events der Integration:

* ``ticket_system_ticket_created``  – Info an das Team, bei "Kritisch" zusätzlich TTS
* ``ticket_system_ticket_updated``  – Info an den Ersteller, wenn ein Ticket
  auf "Abgeschlossen" gesetzt wurde

Zusätzlich stellt :meth:`TicketNotifier.async_notify_ticket` die Benachrichtigung
für den Service ``ticket_system.notify`` bereit (Info oder Erinnerung an
beliebige Empfänger).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Final

from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_AUTHOR,
    ATTR_DESCRIPTION,
    ATTR_PRIORITY,
    ATTR_STATUS,
    ATTR_TITLE,
    CONF_CREATOR_NOTIFY_SERVICES,
    CONF_NOTIFY_CRITICAL_TTS,
    CONF_NOTIFY_ON_CLOSE,
    CONF_NOTIFY_ON_CREATE,
    CONF_NOTIFY_SERVICES,
    CONF_TTS_ENTITY,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_MESSAGE,
    DATA_NOTIFIER,
    DEFAULT_OPTIONS,
    DEFAULT_TTS_MESSAGE,
    DOMAIN,
    EVENT_TICKET_CREATED,
    EVENT_TICKET_UPDATED,
    NOTIFY_KIND_INFO,
    NOTIFY_KIND_REMINDER,
    NOTIFY_TARGET_ALL,
    NOTIFY_TARGET_CREATOR,
    PRIORITY_CRITICAL,
    PRIORITY_LABELS,
    STATUS_CLOSED,
    STATUS_LABELS,
)

_LOGGER = logging.getLogger(__name__)

NOTIFY_DOMAIN: Final = "notify"
ALEXA_NOTIFY_SERVICE: Final = "alexa_media"

MAX_DESCRIPTION_IN_MESSAGE = 500


class TicketNotifier:
    """Erzeugt Benachrichtigungen und Sprachausgaben zu Tickets."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self.hass = hass
        self.entry = entry
        self._unsubs: list[Callable[[], None]] = []
        self._warned: set[str] = set()

    # ------------------------------------------------------------------
    # Lebenszyklus
    # ------------------------------------------------------------------
    @callback
    def async_start(self) -> None:
        """Hängt sich an die Ticket-Events."""
        self._unsubs.append(
            self.hass.bus.async_listen(EVENT_TICKET_CREATED, self._handle_created)
        )
        self._unsubs.append(
            self.hass.bus.async_listen(EVENT_TICKET_UPDATED, self._handle_updated)
        )
        _LOGGER.debug("Ticketsystem: Benachrichtigungen aktiv")

    @callback
    def async_stop(self) -> None:
        """Entfernt alle Event-Listener."""
        while self._unsubs:
            self._unsubs.pop()()

    # ------------------------------------------------------------------
    # Konfiguration
    # ------------------------------------------------------------------
    def config(self) -> dict[str, Any]:
        """Aktuelle Optionen inklusive Standardwerten."""
        conf: dict[str, Any] = {}
        for key, value in DEFAULT_OPTIONS.items():
            conf[key] = list(value) if isinstance(value, list) else value
        conf.update(getattr(self.entry, "options", None) or {})
        return conf

    # ------------------------------------------------------------------
    # Ereignisse
    # ------------------------------------------------------------------
    @callback
    def _handle_created(self, event: Event) -> None:
        """Neues Ticket: Team informieren, kritische Tickets ansagen."""
        ticket = _ticket_from_event(event)
        if ticket is None:
            return

        conf = self.config()
        if not conf[CONF_NOTIFY_ON_CREATE]:
            _LOGGER.debug("Ticketsystem: Benachrichtigung bei neuen Tickets ist deaktiviert")
            return
        if not ticket.get("notify", True):
            _LOGGER.debug(
                "Ticketsystem: Ticket %s ohne Benachrichtigung erstellt",
                ticket.get("id"),
            )
            return

        self.hass.async_create_task(self._async_announce_created(ticket, conf))

    @callback
    def _handle_updated(self, event: Event) -> None:
        """Ticket abgeschlossen: Ersteller informieren."""
        ticket = _ticket_from_event(event)
        if ticket is None:
            return

        changes = event.data.get("changes") or []
        if "status" not in changes or ticket.get(ATTR_STATUS) != STATUS_CLOSED:
            return

        conf = self.config()
        if not conf[CONF_NOTIFY_ON_CLOSE]:
            _LOGGER.debug("Ticketsystem: Benachrichtigung bei Abschluss ist deaktiviert")
            return

        self.hass.async_create_task(self._async_announce_closed(ticket, conf))

    async def _async_announce_created(
        self, ticket: dict[str, Any], conf: dict[str, Any]
    ) -> None:
        """Info an das Team und ggf. Sprachausgabe."""
        title = f"Neues Ticket: {ticket.get(ATTR_TITLE, 'Ohne Titel')}"
        result = await self._async_send_to_services(
            conf.get(CONF_NOTIFY_SERVICES) or [],
            _created_message(ticket),
            title,
        )
        _LOGGER.debug(
            "Ticketsystem: Benachrichtigung zu neuem Ticket %s – gesendet: %s, fehlgeschlagen: %s",
            ticket.get("id"),
            result["sent"],
            result["failed"],
        )

        if (
            ticket.get(ATTR_PRIORITY) == PRIORITY_CRITICAL
            and conf[CONF_NOTIFY_CRITICAL_TTS]
        ):
            await self._async_speak(_tts_message(conf, ticket))

    async def _async_announce_closed(
        self, ticket: dict[str, Any], conf: dict[str, Any]
    ) -> None:
        """Info an den Ersteller, dass das Ticket erledigt ist."""
        services = conf.get(CONF_CREATOR_NOTIFY_SERVICES) or conf.get(
            CONF_NOTIFY_SERVICES
        )
        title = f"Ticket abgeschlossen: {ticket.get(ATTR_TITLE, 'Ohne Titel')}"
        priority = PRIORITY_LABELS.get(
            str(ticket.get(ATTR_PRIORITY)), str(ticket.get(ATTR_PRIORITY) or "–")
        )
        message = "\n".join(
            [
                f"Das Ticket „{ticket.get(ATTR_TITLE, 'Ohne Titel')}“ wurde abgeschlossen.",
                "",
                f"Ersteller: {ticket.get(ATTR_AUTHOR) or 'Unbekannt'}",
                f"Dringlichkeit: {priority}",
                f"ID: {ticket.get('id', '–')}",
            ]
        )
        result = await self._async_send_to_services(services or [], message, title)
        _LOGGER.debug(
            "Ticketsystem: Abschluss-Info zu Ticket %s – gesendet: %s, fehlgeschlagen: %s",
            ticket.get("id"),
            result["sent"],
            result["failed"],
        )

    # ------------------------------------------------------------------
    # Service ticket_system.notify
    # ------------------------------------------------------------------
    async def async_notify_ticket(
        self,
        ticket: dict[str, Any],
        *,
        kind: str = NOTIFY_KIND_INFO,
        target: str = "admins",
        message: str | None = None,
        title: str | None = None,
        service: str | None = None,
    ) -> dict[str, Any]:
        """Verschickt eine Info oder Erinnerung zu einem bestehenden Ticket."""
        conf = self.config()
        team_services = list(conf.get(CONF_NOTIFY_SERVICES) or [])
        creator_services = list(conf.get(CONF_CREATOR_NOTIFY_SERVICES) or [])

        if service:
            services = [service]
        elif target == NOTIFY_TARGET_CREATOR:
            services = creator_services or team_services
        elif target == NOTIFY_TARGET_ALL:
            services = team_services + creator_services
        else:
            services = team_services

        ticket_title = ticket.get(ATTR_TITLE) or "Ohne Titel"
        if title:
            final_title = title
        elif kind == NOTIFY_KIND_REMINDER:
            final_title = f"Erinnerung: {ticket_title}"
        else:
            final_title = f"Ticket: {ticket_title}"

        final_message = message or (
            _reminder_message(ticket)
            if kind == NOTIFY_KIND_REMINDER
            else _info_message(ticket)
        )

        result = await self._async_send_to_services(
            services, final_message, final_title
        )
        return {"ticket_id": ticket.get("id"), **result}

    # ------------------------------------------------------------------
    # Versand
    # ------------------------------------------------------------------
    async def _async_send_to_services(
        self, services: list[Any], message: str, title: str
    ) -> dict[str, list[str]]:
        """Sendet eine Nachricht über alle brauchbaren notify-Dienste."""
        sent: list[str] = []
        failed: list[str] = []

        for name in _normalize_services(services):
            if not self.hass.services.has_service(NOTIFY_DOMAIN, name):
                self._warn_once(
                    f"notify.{name}",
                    f"Ticketsystem: Der Benachrichtigungsdienst notify.{name} existiert "
                    "nicht (mehr) und wird übersprungen. Bitte die Optionen der "
                    "Integration prüfen.",
                )
                continue

            try:
                await self.hass.services.async_call(
                    NOTIFY_DOMAIN,
                    name,
                    {
                        "message": message,
                        "title": title,
                        "data": {"title": title},
                    },
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001 - ein Dienst darf die anderen nicht blockieren
                _LOGGER.warning(
                    "Ticketsystem: Benachrichtigung über notify.%s fehlgeschlagen: %s",
                    name,
                    err,
                )
                failed.append(f"notify.{name}")
            else:
                sent.append(f"notify.{name}")

        if not sent and not failed:
            _LOGGER.debug(
                "Ticketsystem: Keine Benachrichtigungsdienste konfiguriert – "
                "Nachricht wurde nicht versendet"
            )

        return {"sent": sent, "failed": failed}

    async def _async_speak(self, text: str) -> None:
        """Gibt einen Text auf den konfigurierten Mediaplayern aus."""
        conf = self.config()
        players = [
            player
            for player in conf.get(CONF_TTS_MEDIA_PLAYERS) or []
            if isinstance(player, str) and player
        ]
        if not players:
            _LOGGER.debug(
                "Ticketsystem: Kein Mediaplayer für die Sprachausgabe konfiguriert"
            )
            return

        tts_entity = conf.get(CONF_TTS_ENTITY)
        if isinstance(tts_entity, str) and tts_entity:
            if not self.hass.services.has_service("tts", "speak"):
                self._warn_once(
                    "tts.speak",
                    "Ticketsystem: tts.speak ist nicht verfügbar – die "
                    "Sprachausgabe kritischer Tickets wird übersprungen.",
                )
                return

            for player in players:
                try:
                    await self.hass.services.async_call(
                        "tts",
                        "speak",
                        {
                            "entity_id": tts_entity,
                            "media_player_entity_id": player,
                            "message": text,
                            "cache": True,
                        },
                        blocking=True,
                    )
                    continue
                except Exception as err:  # noqa: BLE001 - ein Player darf die anderen nicht blockieren
                    # Echo-Geräte (Alexa Media Player) nehmen die von tts.speak
                    # gestreamte Audiodatei nicht an und antworten z. B. mit
                    # "music is not available as a music provider". Dort klappt
                    # die Ansage über notify.alexa_media mit type: tts.
                    alexa_err = await self._async_alexa_speak(player, text)
                    if alexa_err is None:
                        continue
                    _LOGGER.warning(
                        "Ticketsystem: Sprachausgabe auf %s fehlgeschlagen: %s "
                        "(Alexa-Ausgabe ebenfalls: %s)",
                        player,
                        err,
                        alexa_err,
                    )
            return

        # Ohne TTS-Entität: Alexa Media Player unterstützt Sprachausgaben direkt
        if self.hass.services.has_service(NOTIFY_DOMAIN, ALEXA_NOTIFY_SERVICE):
            for player in players:
                err = await self._async_alexa_speak(player, text)
                if err is not None:
                    _LOGGER.warning(
                        "Ticketsystem: Alexa-Sprachausgabe auf %s fehlgeschlagen: %s",
                        player,
                        err,
                    )
            return

        self._warn_once(
            "tts-missing",
            "Ticketsystem: Für die Sprachausgabe kritischer Tickets fehlt eine "
            "TTS-Entität (tts.*) in den Optionen – oder Alexa Media Player. "
            "Die Benachrichtigung selbst wurde trotzdem gesendet.",
        )

    async def _async_alexa_speak(self, player: str, text: str) -> Exception | None:
        """Spricht einen Text über Alexa Media Player.

        Gibt ``None`` zurück, wenn die Ansage abgeschickt wurde, sonst den
        aufgetretenen Fehler (oder einen Hinweis, falls der Dienst fehlt).
        """
        if not self.hass.services.has_service(NOTIFY_DOMAIN, ALEXA_NOTIFY_SERVICE):
            return RuntimeError(f"notify.{ALEXA_NOTIFY_SERVICE} ist nicht verfügbar")
        try:
            await self.hass.services.async_call(
                NOTIFY_DOMAIN,
                ALEXA_NOTIFY_SERVICE,
                {
                    "message": text,
                    "target": player,
                    "data": {"type": "tts"},
                },
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            return err
        _LOGGER.debug(
            "Ticketsystem: Ansage über notify.%s auf %s gesendet",
            ALEXA_NOTIFY_SERVICE,
            player,
        )
        return None

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def _warn_once(self, key: str, message: str) -> None:
        """Warnung pro Sitzung nur einmal ins Log schreiben."""
        if key in self._warned:
            return
        self._warned.add(key)
        _LOGGER.warning(message)


def get_notifier(hass: HomeAssistant) -> TicketNotifier | None:
    """Aktuell aktiven Notifier zurückgeben (oder None)."""
    return hass.data.get(DOMAIN, {}).get(DATA_NOTIFIER)


# ---------------------------------------------------------------------------
# Texte
# ---------------------------------------------------------------------------
def _ticket_from_event(event: Event) -> dict[str, Any] | None:
    """Ticket-Daten aus einem Bus-Event holen."""
    data = event.data or {}
    ticket = data.get("ticket")
    if not isinstance(ticket, dict):
        return None
    return ticket


def _created_message(ticket: dict[str, Any]) -> str:
    """Nachricht für ein neu erstelltes Ticket."""
    priority = PRIORITY_LABELS.get(
        str(ticket.get(ATTR_PRIORITY)), str(ticket.get(ATTR_PRIORITY) or "–")
    )
    status = STATUS_LABELS.get(
        str(ticket.get(ATTR_STATUS)), str(ticket.get(ATTR_STATUS) or "–")
    )
    lines = [
        "Ein neues Ticket wurde erstellt.",
        "",
        f"Titel: {ticket.get(ATTR_TITLE) or 'Ohne Titel'}",
        f"Dringlichkeit: {priority}",
        f"Status: {status}",
        f"Ersteller: {ticket.get(ATTR_AUTHOR) or 'Unbekannt'}",
        f"ID: {ticket.get('id', '–')}",
    ]

    description = str(ticket.get(ATTR_DESCRIPTION) or "").strip()
    if description:
        if len(description) > MAX_DESCRIPTION_IN_MESSAGE:
            description = description[: MAX_DESCRIPTION_IN_MESSAGE - 1].rstrip() + "…"
        lines.extend(["", description])

    return "\n".join(lines)


def _info_message(ticket: dict[str, Any]) -> str:
    """Allgemeine Info zu einem Ticket (Service ticket_system.notify)."""
    priority = PRIORITY_LABELS.get(
        str(ticket.get(ATTR_PRIORITY)), str(ticket.get(ATTR_PRIORITY) or "–")
    )
    status = STATUS_LABELS.get(
        str(ticket.get(ATTR_STATUS)), str(ticket.get(ATTR_STATUS) or "–")
    )
    lines = [
        f"Ticket: {ticket.get(ATTR_TITLE) or 'Ohne Titel'}",
        "",
        f"Dringlichkeit: {priority}",
        f"Status: {status}",
        f"Ersteller: {ticket.get(ATTR_AUTHOR) or 'Unbekannt'}",
        f"ID: {ticket.get('id', '–')}",
    ]

    description = str(ticket.get(ATTR_DESCRIPTION) or "").strip()
    if description:
        if len(description) > MAX_DESCRIPTION_IN_MESSAGE:
            description = description[: MAX_DESCRIPTION_IN_MESSAGE - 1].rstrip() + "…"
        lines.extend(["", description])

    return "\n".join(lines)


def _reminder_message(ticket: dict[str, Any]) -> str:
    """Erinnerung an ein noch offenes Ticket."""
    priority = PRIORITY_LABELS.get(
        str(ticket.get(ATTR_PRIORITY)), str(ticket.get(ATTR_PRIORITY) or "–")
    )
    return "\n".join(
        [
            f"Erinnerung: „{ticket.get(ATTR_TITLE) or 'Ohne Titel'}“ wartet auf Bearbeitung.",
            "",
            f"Dringlichkeit: {priority}",
            f"Eingegangen: {_age_text(ticket.get('created_at'))}",
            f"Ersteller: {ticket.get(ATTR_AUTHOR) or 'Unbekannt'}",
            f"ID: {ticket.get('id', '–')}",
        ]
    )


def _age_text(created_at: Any) -> str:
    """Alter eines Tickets als lesbarer Text."""
    created = _parse_timestamp(created_at)
    if created is None:
        return "unbekannt"

    delta = datetime.now(timezone.utc) - created
    if delta.total_seconds() < 0:
        return "gerade eben"

    days = delta.days
    if days >= 2:
        return f"seit {days} Tagen"
    if days == 1:
        return "seit 1 Tag"

    hours = int(delta.total_seconds() // 3600)
    if hours >= 2:
        return f"seit {hours} Stunden"
    if hours == 1:
        return "seit 1 Stunde"
    return "seit wenigen Minuten"


def _parse_timestamp(value: Any) -> datetime | None:
    """ISO-8601-Zeitstempel tolerant einlesen."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _tts_message(conf: dict[str, Any], ticket: dict[str, Any]) -> str:
    """Sprachtext aus dem konfigurierten Template bauen."""
    template = conf.get(CONF_TTS_MESSAGE) or DEFAULT_TTS_MESSAGE
    values = {
        "title": ticket.get(ATTR_TITLE) or "Ohne Titel",
        "priority": PRIORITY_LABELS.get(
            str(ticket.get(ATTR_PRIORITY)), str(ticket.get(ATTR_PRIORITY) or "")
        ),
        "priority_key": ticket.get(ATTR_PRIORITY) or "",
        "author": ticket.get(ATTR_AUTHOR) or "Unbekannt",
        "id": ticket.get("id") or "",
    }
    try:
        return str(template).format_map(_SafeDict(values))
    except (ValueError, IndexError, AttributeError):
        _LOGGER.warning(
            "Ticketsystem: Ungültiges TTS-Template %r – es wird der Standardtext "
            "gesprochen",
            template,
        )
        return DEFAULT_TTS_MESSAGE.format_map(_SafeDict(values))


class _SafeDict(dict[str, Any]):
    """Lässt unbekannte Platzhalter im Text stehen, statt zu scheitern."""

    def __missing__(self, key: str) -> str:  # noqa: D105
        return "{" + key + "}"


def _normalize_services(services: list[Any]) -> list[str]:
    """Dienstnamen vereinheitlichen (``notify.x`` und ``x`` erlaubt), ohne Dubletten."""
    result: list[str] = []
    for service in services:
        if not isinstance(service, str):
            continue
        name = service.strip()
        if name.startswith(f"{NOTIFY_DOMAIN}."):
            name = name[len(NOTIFY_DOMAIN) + 1 :]
        if not name or name in result:
            continue
        result.append(name)
    return result
