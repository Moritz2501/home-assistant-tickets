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
NOTIFY_SEND_MESSAGE: Final = "send_message"
ALEXA_NOTIFY_SERVICE: Final = "alexa_media"
TTS_DOMAIN: Final = "tts"
TTS_SERVICE: Final = "speak"
# Die Entitäts-IDs der Alexa-Devices-Notify-Entitäten entstehen aus den
# übersetzten Namen (englisch ``_announce``/``_speak``, deutsch u. a.
# ``_durchsagen``/``_sprechen``), deshalb mehrere Varianten plus der
# sprachunabhängige ``translation_key`` aus der Entity-Registry.
ALEXA_NOTIFY_SUFFIXES: Final = (
    "_announce",
    "_speak",
    "_durchsagen",
    "_sprechen",
    "_ansage",
    "_ankuendigung",
    "_ankündigung",
)
ALEXA_NOTIFY_KEYS: Final = ("announce", "speak")
ALEXA_DEVICES_DOMAIN: Final = "alexa_devices"

MAX_DESCRIPTION_IN_MESSAGE = 500


def _registry_entry(hass: HomeAssistant, entity_id: str) -> Any:
    """Registry-Eintrag einer Entität oder ``None`` (Registry ist optional)."""
    try:
        from homeassistant.helpers import entity_registry as er

        return er.async_get(hass).async_get(entity_id)
    except Exception:  # noqa: BLE001 - Registry ist nur eine Zusatzquelle
        return None


def _alexa_notify_entities(hass: HomeAssistant, player: str) -> list[str]:
    """Liefert Speak-/Announce-Entitäten, die zu einem Alexa-Player gehören.

    Die Integration ``alexa_devices`` legt pro Gerät Speak- und Announce-Entitäten
    an (``notify.<gerät>_speak``/``_announce``, in übersetzten Installationen
    z. B. ``notify.moritz_sprechen``). Ansagen laufen dort über
    ``notify.send_message``, während ``media_player.play_media`` (der Weg von
    ``tts.speak``) bei Echo-Geräten mit "music is not available as a music
    provider" abbricht.

    Announce steht vor Speak: es meldet sich mit Signalton, das ist für
    kritische Tickets deutlicher.
    """
    base = player.split(".", 1)[1] if "." in player else player
    prefix = f"{NOTIFY_DOMAIN}.{base}"
    states = getattr(hass, "states", None)
    found: list[str] = []

    def _add(entity_id: str | None) -> None:
        if entity_id and entity_id not in found:
            found.append(entity_id)

    # 1) Erwartete Namen
    if states is not None:
        for suffix in ALEXA_NOTIFY_SUFFIXES:
            entity_id = f"{prefix}{suffix}"
            if states.get(entity_id) is not None:
                _add(entity_id)

    # 2) Gerät aus der Registry: Namen sind lokalisiert, der translation_key nicht
    entry = _registry_entry(hass, player)
    device_id = getattr(entry, "device_id", None)
    if device_id:
        try:
            from homeassistant.helpers import entity_registry as er

            siblings = [
                item
                for item in er.async_entries_for_device(er.async_get(hass), device_id)
                if item.domain == NOTIFY_DOMAIN
                and not getattr(item, "disabled_by", None)
            ]
        except Exception:  # noqa: BLE001
            siblings = []
        for key in ALEXA_NOTIFY_KEYS:
            for item in siblings:
                if getattr(item, "translation_key", None) == key:
                    _add(item.entity_id)
        if not found and len(siblings) == 1:
            _add(siblings[0].entity_id)
        for suffix in ALEXA_NOTIFY_SUFFIXES:
            for item in siblings:
                if item.entity_id.endswith(suffix):
                    _add(item.entity_id)

    # 3) Notfall: Notify-Entitäten, deren ID mit dem Gerätenamen beginnt
    if not found and states is not None:
        try:
            entity_ids = states.async_entity_ids(NOTIFY_DOMAIN)
        except Exception:  # noqa: BLE001
            entity_ids = []
        for entity_id in entity_ids:
            if entity_id.startswith(f"{prefix}_") and entity_id.endswith(
                ALEXA_NOTIFY_SUFFIXES
            ):
                _add(entity_id)

    return found


def _is_alexa_player(hass: HomeAssistant, player: str) -> bool:
    """True, wenn der Player von der Integration ``alexa_devices`` stammt."""
    entry = _registry_entry(hass, player)
    platform = getattr(entry, "platform", None)
    return platform == ALEXA_DEVICES_DOMAIN


def _alexa_media_service(hass: HomeAssistant) -> str | None:
    """Sucht den Notify-Dienst von Alexa Media Player.

    Je nach Version heißt er ``notify.alexa_media`` oder pro Konto
    ``notify.alexa_media_<konto>``; ``alexa_media_last_called`` wird ausgelassen,
    weil er ein eigenes Ziel mitbringt.
    """
    services = getattr(hass.services, "async_services", None)
    names: set[str] = set()
    if callable(services):
        try:
            names = set(services().get(NOTIFY_DOMAIN) or {})
        except Exception:  # noqa: BLE001
            names = set()

    if ALEXA_NOTIFY_SERVICE in names:
        return ALEXA_NOTIFY_SERVICE
    for name in sorted(names):
        if name.startswith(ALEXA_NOTIFY_SERVICE) and not name.endswith("last_called"):
            return name
    if not names and hass.services.has_service(NOTIFY_DOMAIN, ALEXA_NOTIFY_SERVICE):
        return ALEXA_NOTIFY_SERVICE
    return None


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
        tts_configured = isinstance(tts_entity, str) and bool(tts_entity)
        tts_available = tts_configured and self.hass.services.has_service(
            TTS_DOMAIN, TTS_SERVICE
        )
        alexa_service = _alexa_media_service(self.hass)

        if tts_configured and not tts_available:
            self._warn_once(
                "tts.speak",
                "Ticketsystem: tts.speak ist nicht verfügbar – die "
                "Sprachausgabe kritischer Tickets läuft nur noch über eine "
                "Alexa-Integration, falls eine eingerichtet ist.",
            )

        for player in players:
            errors: list[str] = []
            handled = False

            # 1) Alexa-Geräte (Integration "Alexa Devices"): Speak-/Announce-Entität
            #    des Geräts. Deren Mediaplayer nimmt keine gestreamten Dateien an.
            notify_entities = _alexa_notify_entities(self.hass, player)
            for entity_id in notify_entities:
                err = await self._async_notify_entity(entity_id, text)
                if err is None:
                    handled = True
                    break
                errors.append(f"{entity_id}: {err}")
            if handled:
                continue

            # Echo-Geräte lehnen die von tts.speak gestreamte Audiodatei ab
            # ("music is not available as a music provider") – dort wird der Weg
            # gar nicht erst versucht, sonst stünde der Fehler wieder im Log.
            echo = bool(notify_entities) or _is_alexa_player(self.hass, player)
            if echo and not notify_entities:
                errors.append(
                    "keine Speak-/Announce-Entität am Gerät gefunden "
                    "(in der Alexa-App Durchsagen erlauben, Nicht-stören aus)"
                )

            # 2) Klassischer Weg über tts.speak (Cast, Sonos, ...)
            if tts_available and not echo:
                try:
                    await self.hass.services.async_call(
                        TTS_DOMAIN,
                        TTS_SERVICE,
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
                    errors.append(f"tts.speak: {err}")

            # 3) Alexa Media Player (Custom-Integration) als letzter Weg
            if alexa_service is not None:
                err = await self._async_alexa_speak(player, text, alexa_service)
                if err is None:
                    continue
                errors.append(f"notify.{alexa_service}: {err}")

            if errors:
                _LOGGER.warning(
                    "Ticketsystem: Sprachausgabe auf %s fehlgeschlagen: %s",
                    player,
                    "; ".join(errors),
                )

        if not tts_configured and alexa_service is None:
            if not any(_alexa_notify_entities(self.hass, player) for player in players):
                self._warn_once(
                    "tts-missing",
                    "Ticketsystem: Für die Sprachausgabe kritischer Tickets fehlt "
                    "eine TTS-Entität (tts.*) in den Optionen – oder eine "
                    "Alexa-Integration (Alexa Devices, Alexa Media Player). Die "
                    "Benachrichtigung selbst wurde trotzdem gesendet.",
                )

    async def _async_notify_entity(self, entity_id: str, text: str) -> Exception | None:
        """Spricht Text über eine Speak-/Announce-Entität (``alexa_devices``)."""
        if not self.hass.services.has_service(NOTIFY_DOMAIN, NOTIFY_SEND_MESSAGE):
            return RuntimeError(
                f"{NOTIFY_DOMAIN}.{NOTIFY_SEND_MESSAGE} ist nicht verfügbar"
            )
        try:
            await self.hass.services.async_call(
                NOTIFY_DOMAIN,
                NOTIFY_SEND_MESSAGE,
                {"message": text},
                blocking=True,
                target={"entity_id": entity_id},
            )
        except Exception as err:  # noqa: BLE001
            return err
        _LOGGER.debug("Ticketsystem: Ansage über %s gesendet", entity_id)
        return None

    async def _async_alexa_speak(
        self, player: str, text: str, service: str = ALEXA_NOTIFY_SERVICE
    ) -> Exception | None:
        """Spricht einen Text über Alexa Media Player.

        ``service`` ist der Dienstname unter ``notify`` – je nach Version von
        Alexa Media Player ``alexa_media`` oder ``alexa_media_<konto>``.
        """
        try:
            await self.hass.services.async_call(
                NOTIFY_DOMAIN,
                service,
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
            "Ticketsystem: Ansage über notify.%s auf %s gesendet", service, player
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
