"""Config Flow für das Ticketsystem."""

from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_CREATOR_NOTIFY_SERVICES,
    CONF_NAME,
    CONF_NOTIFY_CRITICAL_TTS,
    CONF_NOTIFY_ON_CLOSE,
    CONF_NOTIFY_ON_CREATE,
    CONF_NOTIFY_SERVICES,
    CONF_TTS_ENTITY,
    CONF_TTS_MEDIA_PLAYERS,
    CONF_TTS_MESSAGE,
    CONF_TTS_VOLUME,
    DEFAULT_NAME,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from .notifications import NOTIFY_DOMAIN


class TicketSystemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einmalige Einrichtung über die Home-Assistant-Oberfläche."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einrichtungsdialog."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or DEFAULT_NAME).strip()
            return self.async_create_entry(title=name or DEFAULT_NAME, data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Optional(CONF_NAME, default=DEFAULT_NAME): str}
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TicketSystemOptionsFlow:
        """Options-Flow für die Benachrichtigungen bereitstellen."""
        return TicketSystemOptionsFlow()


class TicketSystemOptionsFlow(OptionsFlow):
    """Einstellungen für Benachrichtigungen und Sprachausgabe."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Formular anzeigen bzw. Eingaben speichern."""
        if user_input is not None:
            return self.async_create_entry(data=_normalize_options(user_input))

        options = dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.hass, options),
            # Die Platzhalter dokumentieren die Variablen des TTS-Templates. Sie
            # werden als reiner Text übergeben, weil das Frontend die
            # Beschreibung als ICU-Nachricht formatiert und unbekannte
            # Variablen sonst als Fehler protokolliert (MISSING_VALUE).
            description_placeholders={
                "title": "{title}",
                "priority": "{priority}",
                "author": "{author}",
                "id": "{id}",
            },
        )


# Dienste der notify-Domäne, die keine Benachrichtigung verschicken.
_IGNORED_NOTIFY_SERVICES: Final = {"send_message", "reload_services"}


def _options_schema(hass: HomeAssistant, options: dict[str, Any]) -> vol.Schema:
    """Schema mit den aktuell gespeicherten Werten als Standard."""

    def current(key: str) -> Any:
        value = options.get(key, DEFAULT_OPTIONS.get(key))
        if isinstance(value, list):
            return list(value)
        return value

    return vol.Schema(
        {
            vol.Optional(
                CONF_NOTIFY_SERVICES, default=current(CONF_NOTIFY_SERVICES)
            ): _notify_selector(hass, current(CONF_NOTIFY_SERVICES)),
            vol.Optional(
                CONF_CREATOR_NOTIFY_SERVICES,
                default=current(CONF_CREATOR_NOTIFY_SERVICES),
            ): _notify_selector(hass, current(CONF_CREATOR_NOTIFY_SERVICES)),
            vol.Optional(
                CONF_NOTIFY_ON_CREATE, default=current(CONF_NOTIFY_ON_CREATE)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_CLOSE, default=current(CONF_NOTIFY_ON_CLOSE)
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_CRITICAL_TTS,
                default=current(CONF_NOTIFY_CRITICAL_TTS),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_TTS_ENTITY, default=current(CONF_TTS_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="tts")
            ),
            vol.Optional(
                CONF_TTS_MEDIA_PLAYERS, default=current(CONF_TTS_MEDIA_PLAYERS)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="media_player", multiple=True
                )
            ),
            vol.Optional(
                CONF_TTS_MESSAGE, default=current(CONF_TTS_MESSAGE)
            ): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            vol.Optional(
                CONF_TTS_VOLUME, default=current(CONF_TTS_VOLUME)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=5,
                    mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="%",
                )
            ),
        }
    )


def _notify_selector(hass: HomeAssistant, selected: Any) -> selector.SelectSelector:
    """Mehrfachauswahl der vorhandenen notify-Dienste (inkl. Freitext)."""
    services = hass.services.async_services().get(NOTIFY_DOMAIN, {})
    values = [
        f"{NOTIFY_DOMAIN}.{name}"
        for name in sorted(services)
        if name not in _IGNORED_NOTIFY_SERVICES
    ]

    # Bereits gespeicherte Dienste behalten, auch wenn sie gerade fehlen.
    for name in selected or []:
        if isinstance(name, str) and name and name not in values:
            values.append(name)

    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=values,
            multiple=True,
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _normalize_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Gespeicherte Optionen in eine verlässliche Form bringen."""
    services = _clean_services(user_input.get(CONF_NOTIFY_SERVICES))
    creators = _clean_services(user_input.get(CONF_CREATOR_NOTIFY_SERVICES))
    players = [
        player
        for player in user_input.get(CONF_TTS_MEDIA_PLAYERS) or []
        if isinstance(player, str) and player
    ]

    tts_entity = user_input.get(CONF_TTS_ENTITY)
    if not isinstance(tts_entity, str) or not tts_entity:
        tts_entity = None

    tts_message = str(user_input.get(CONF_TTS_MESSAGE) or "").strip()
    tts_volume = _clean_volume(user_input.get(CONF_TTS_VOLUME))

    return {
        CONF_NOTIFY_SERVICES: services,
        CONF_CREATOR_NOTIFY_SERVICES: creators,
        CONF_NOTIFY_ON_CREATE: bool(user_input.get(CONF_NOTIFY_ON_CREATE, True)),
        CONF_NOTIFY_ON_CLOSE: bool(user_input.get(CONF_NOTIFY_ON_CLOSE, True)),
        CONF_NOTIFY_CRITICAL_TTS: bool(
            user_input.get(CONF_NOTIFY_CRITICAL_TTS, True)
        ),
        CONF_TTS_ENTITY: tts_entity,
        CONF_TTS_MEDIA_PLAYERS: players,
        CONF_TTS_MESSAGE: tts_message or DEFAULT_OPTIONS[CONF_TTS_MESSAGE],
        CONF_TTS_VOLUME: tts_volume,
    }


def _clean_volume(value: Any) -> int:
    """Lautstärke in Prozent (0–100); 0 bedeutet "nicht ändern"."""
    try:
        volume = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_OPTIONS[CONF_TTS_VOLUME]
    return max(0, min(100, volume))


def _clean_services(value: Any) -> list[str]:
    """Dienstnamen aus dem Selector säubern."""
    result: list[str] = []
    for service in value or []:
        if not isinstance(service, str):
            continue
        name = service.strip()
        if name and name not in result:
            result.append(name)
    return result
