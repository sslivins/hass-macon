"""Describe Macon fault events in the Home Assistant activity log."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_MACON_FAULT


def _fault_message(data: Mapping[str, Any]) -> str:
    if not data.get("active"):
        return "fault cleared"
    code = data.get("code") or "unknown"
    description = data.get("description") or data.get("name")
    if description:
        return f"reported fault {code}: {description}"
    return f"reported fault {code}"


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[Event], dict[str, str]]], None
    ],
) -> None:
    """Describe macon_fault events so the fault is explained in Activity."""

    @callback
    def async_describe_fault(event: Event) -> dict[str, str]:
        data = event.data
        controller_id = data.get("device_id")
        name = "Heat pump"
        entry: dict[str, str] = {}
        entity_registry = er.async_get(hass)
        # Events recorded before entity_id was added still get linked.
        fault_entity = data.get("entity_id") or (
            entity_registry.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, f"{controller_id}_fault_code"
            )
            if controller_id
            else None
        )
        if fault_entity is not None:
            entry[LOGBOOK_ENTRY_ENTITY_ID] = fault_entity
            registry_entry = entity_registry.async_get(fault_entity)
            device_id = registry_entry.device_id if registry_entry else None
            device = (
                dr.async_get(hass).async_get(device_id) if device_id else None
            )
            if device is not None:
                name = device.name_by_user or device.name or name
        entry[LOGBOOK_ENTRY_NAME] = name
        entry[LOGBOOK_ENTRY_MESSAGE] = _fault_message(data)
        return entry

    async_describe_event(DOMAIN, EVENT_MACON_FAULT, async_describe_fault)
