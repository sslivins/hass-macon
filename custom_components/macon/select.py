"""Exact Macon working-mode selection."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import normalize_mode
from .entity import MaconEntity
from .runtime import MaconRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MaconModeSelect(entry.runtime_data)])


class MaconModeSelect(MaconEntity, SelectEntity):
    """Expose the exact server-advertised Macon mode allowlist."""

    _attr_name = "Selected mode"
    _attr_translation_key = "mode"

    def __init__(self, runtime: MaconRuntime) -> None:
        super().__init__(runtime, "mode")

    @property
    def options(self) -> list[str]:
        capabilities = self.runtime.client.capabilities
        if capabilities is None:
            return []
        return [normalize_mode(mode) for mode in capabilities.supported_modes]

    @property
    def current_option(self) -> str | None:
        snapshot = self.runtime.snapshot
        if snapshot is None:
            return None
        mode = normalize_mode(snapshot.state.mode)
        return mode if mode in self.options else None

    @property
    def available(self) -> bool:
        capabilities = self.runtime.client.capabilities
        return (
            super().available
            and capabilities is not None
            and capabilities.control_mode
            and bool(capabilities.supported_modes)
        )

    async def async_select_option(self, option: str) -> None:
        capabilities = self.runtime.client.capabilities
        # Send the key the controller advertised; older firmware uses the
        # pre-rename names.
        key = None
        if capabilities is not None and capabilities.control_mode:
            key = next(
                (
                    mode
                    for mode in capabilities.supported_modes
                    if normalize_mode(mode) == option
                ),
                None,
            )
        if key is None:
            raise HomeAssistantError(
                "The selected Macon mode is not currently supported"
            )
        await self.runtime.client.async_set_mode(key)
