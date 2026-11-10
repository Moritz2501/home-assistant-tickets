"""Config Flow für das Ticketsystem."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN


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
