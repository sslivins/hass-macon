"""Redacted diagnostics for the Macon Heat Pump Controller integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .runtime import MaconRuntime

# The device id is the controller's MAC; together with the address, hostname,
# and Wi-Fi network it would identify and locate the installation.
TO_REDACT = {
    "device_id",
    "ip_address",
    "local_hostname",
    "wifi_ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return useful state without identity, address, or credentials."""
    runtime: MaconRuntime = entry.runtime_data
    snapshot = runtime.snapshot
    capabilities = runtime.client.capabilities
    controller = runtime.diagnostics
    data = {
        "entry": {
            "device_id": entry.unique_id,
            "port": entry.data["port"],
        },
        "status": {
            "available": runtime.status.available,
            "stream_connected": runtime.status.stream_connected,
            "last_error_type": (
                type(runtime.status.last_error).__name__
                if runtime.status.last_error is not None
                else None
            ),
        },
        "capabilities": (
            asdict(capabilities) if capabilities is not None else None
        ),
        "controller_diagnostics": {
            "ok": runtime.diagnostics_ok,
            "boot_time": (
                runtime.boot_time.isoformat()
                if runtime.boot_time is not None
                else None
            ),
            "data": asdict(controller) if controller is not None else None,
        },
        "snapshot": asdict(snapshot) if snapshot is not None else None,
    }
    return async_redact_data(data, TO_REDACT)
