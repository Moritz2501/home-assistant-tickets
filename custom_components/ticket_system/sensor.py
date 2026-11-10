"""Sensoren, die den Ticketbestand in Home Assistant abbilden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    PRIORITY_CRITICAL,
    SIGNAL_TICKETS_UPDATED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
)
from .manager import TicketManager, get_manager

KIND_ALL = "all"
KIND_CRITICAL = "critical"


@dataclass(frozen=True, kw_only=True)
class TicketSensorDescription(SensorEntityDescription):
    """Sensor-Beschreibung mit zusätzlicher Auswertungsart."""

    kind: str = KIND_ALL


SENSOR_TYPES: tuple[TicketSensorDescription, ...] = (
    TicketSensorDescription(
        key="open_tickets",
        translation_key="open_tickets",
        kind=STATUS_OPEN,
        icon="mdi:ticket-outline",
    ),
    TicketSensorDescription(
        key="in_progress_tickets",
        translation_key="in_progress_tickets",
        kind=STATUS_IN_PROGRESS,
        icon="mdi:ticket-confirmation-outline",
    ),
    TicketSensorDescription(
        key="critical_tickets",
        translation_key="critical_tickets",
        kind=KIND_CRITICAL,
        icon="mdi:alert-circle-outline",
    ),
    TicketSensorDescription(
        key="total_tickets",
        translation_key="total_tickets",
        kind=KIND_ALL,
        icon="mdi:ticket",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren für einen Config Entry anlegen."""
    manager = get_manager(hass)
    if manager is None:
        return

    async_add_entities(
        TicketCountSensor(manager, entry, description)
        for description in SENSOR_TYPES
    )


class TicketCountSensor(SensorEntity):
    """Zählt Tickets – gesamt, nach Status oder kritisch/aktiv."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    entity_description: TicketSensorDescription

    def __init__(
        self,
        manager: TicketManager,
        entry: ConfigEntry,
        description: TicketSensorDescription,
    ) -> None:
        self.entity_description = description
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Ticketsystem",
            model="Lokales Ticketsystem",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Auf Ticket-Änderungen hören."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_TICKETS_UPDATED, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Aktueller Zählerstand."""
        tickets = self._manager.async_list()
        kind = self.entity_description.kind

        if kind == KIND_ALL:
            return len(tickets)
        if kind == KIND_CRITICAL:
            return sum(
                1
                for ticket in tickets
                if ticket["priority"] == PRIORITY_CRITICAL
                and ticket["status"] != STATUS_CLOSED
            )
        return sum(1 for ticket in tickets if ticket["status"] == kind)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Auswertung nach Status und Dringlichkeit."""
        counts = self._manager.async_counts()
        return {
            "by_status": counts["by_status"],
            "by_priority": counts["by_priority"],
        }
