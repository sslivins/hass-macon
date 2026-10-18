"""Describe Macon fault and controller events in the Home Assistant activity log."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_MACON_CONTROLLER, EVENT_MACON_FAULT

# An event the controller recorded more than this long before Home Assistant
# saw it (an outage cut the two off) also says when it really happened.
LATE_EVENT_SECONDS = 120

WIFI_REASONS = {
    "signal_lost": "signal lost",
    "network_not_found": "network not found",
    "auth_failed": "authentication failed",
    "ap_disconnected": "disconnected by the access point",
    "ap_restarted": "access point restarted",
}

WEB_SERVER_CAUSES = {
    "no_memory": "out of memory",
    "no_identity": "no TLS certificate",
    "start_failed": "failed to start",
    "test": "test",
}


def _fault_message(data: Mapping[str, Any]) -> str:
    if not data.get("active"):
        return "fault cleared"
    code = data.get("code") or "unknown"
    description = data.get("description") or data.get("name")
    if description:
        return f"reported fault {code}: {description}"
    return f"reported fault {code}"


def _duration(seconds: Any) -> str | None:
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 0:
        return None
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds} s" if seconds else f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def _controller_message(data: Mapping[str, Any]) -> str:
    event_type = str(data.get("type") or "")
    details = data.get("details")
    if not isinstance(details, Mapping):
        details = {}
    if event_type == "wifi_lost":
        reason = WIFI_REASONS.get(str(details.get("reason_key")))
        suffix = f" ({reason})" if reason else ""
        return f"lost Wi-Fi for over a minute{suffix}"
    if event_type == "wifi_restored":
        down = _duration(details.get("down_s"))
        return f"Wi-Fi restored after {down}" if down else "Wi-Fi restored"
    if event_type == "wifi_unstable":
        drops = details.get("drops")
        if isinstance(drops, int) and not isinstance(drops, bool):
            return f"Wi-Fi unstable: {drops} short drops in the last hour"
        return "Wi-Fi unstable: repeated short drops"
    if event_type == "network_unreachable":
        return "lost its network connection while Wi-Fi stayed up"
    if event_type == "network_recovered":
        recovery = details.get("recovery")
        if recovery == "wifi_bounce":
            return "network connection recovered by reconnecting Wi-Fi"
        if recovery == "reboot":
            return "restarted to recover its network connection"
        return "network connection recovered"
    if event_type == "web_server_down":
        cause = WEB_SERVER_CAUSES.get(str(details.get("cause")))
        return f"web server stopped ({cause})" if cause else "web server stopped"
    if event_type == "web_server_recovered":
        if details.get("recovery") == "reboot":
            return "restarted to recover its web server"
        return "web server restarted"
    if event_type == "application_crash":
        return "crashed and restarted"
    if event_type == "watchdog_reset":
        if details.get("watchdog") == "startup":
            return "restarted during startup, likely after a power interruption"
        return "was restarted by its watchdog"
    if event_type == "brownout_reset":
        return "restarted after its supply voltage dipped (brownout)"
    if event_type == "disconnected":
        return "lost communication with the heat pump"
    return event_type.replace("_", " ") or "reported a problem"


def _late_suffix(data: Mapping[str, Any], event: Event) -> str:
    raw = data.get("timestamp")
    if not isinstance(raw, str):
        return ""
    happened = dt_util.parse_datetime(raw)
    if happened is None:
        return ""
    if (event.time_fired - happened).total_seconds() <= LATE_EVENT_SECONDS:
        return ""
    local: datetime = dt_util.as_local(happened)
    if local.date() == dt_util.as_local(event.time_fired).date():
        return f" (at {local:%H:%M})"
    return f" (at {local:%Y-%m-%d %H:%M})"


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[Event], dict[str, str]]], None
    ],
) -> None:
    """Describe Macon events so they are explained in Activity."""

    def _entry(data: Mapping[str, Any], fallback_key: str) -> dict[str, str]:
        controller_id = data.get("device_id")
        name = "Heat pump"
        entry: dict[str, str] = {}
        entity_registry = er.async_get(hass)
        # Events recorded before entity_id was added still get linked.
        linked = data.get("entity_id") or (
            entity_registry.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, f"{controller_id}_{fallback_key}"
            )
            if controller_id
            else None
        )
        if linked is not None:
            entry[LOGBOOK_ENTRY_ENTITY_ID] = linked
            registry_entry = entity_registry.async_get(linked)
            device_id = registry_entry.device_id if registry_entry else None
            device = (
                dr.async_get(hass).async_get(device_id) if device_id else None
            )
            if device is not None:
                name = device.name_by_user or device.name or name
        entry[LOGBOOK_ENTRY_NAME] = name
        return entry

    @callback
    def async_describe_fault(event: Event) -> dict[str, str]:
        entry = _entry(event.data, "fault_code")
        entry[LOGBOOK_ENTRY_MESSAGE] = _fault_message(event.data)
        return entry

    @callback
    def async_describe_controller(event: Event) -> dict[str, str]:
        data = event.data
        fallback = (
            "wifi_disconnect_count"
            if str(data.get("type") or "").startswith("wifi_")
            else "last_reset_reason"
        )
        entry = _entry(data, fallback)
        entry[LOGBOOK_ENTRY_MESSAGE] = _controller_message(data) + _late_suffix(data, event)
        return entry

    async_describe_event(DOMAIN, EVENT_MACON_FAULT, async_describe_fault)
    async_describe_event(DOMAIN, EVENT_MACON_CONTROLLER, async_describe_controller)
