"""Base entities for one Macon heat pump controller config entry."""

from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity
from pymacon import ControllerDiagnostics

from .runtime import MaconRuntime


class MaconEntity(Entity):
    """Heat-pump entity updated directly by the local-push runtime."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: MaconRuntime, key: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.device_id}_{key}"
        self._attr_device_info = runtime.device_info

    @property
    def available(self) -> bool:
        return self.runtime.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.runtime.async_add_listener(
                self._async_runtime_updated
            )
        )

    def _async_runtime_updated(self) -> None:
        self.async_write_ha_state()


class MaconControllerEntity(MaconEntity):
    """Entity that belongs to the Arctic controller device."""

    def __init__(self, runtime: MaconRuntime, key: str) -> None:
        super().__init__(runtime, key)
        self._attr_device_info = runtime.controller_device_info


class MaconControllerDiagnosticEntity(MaconControllerEntity):
    """Controller-health entity driven by the diagnostics poll.

    Listens only to diagnostics refreshes, and goes unavailable on its own
    when diagnostics are unsupported or failing, without touching the
    heat-pump entities.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def diagnostics(self) -> ControllerDiagnostics | None:
        return self.runtime.diagnostics

    @property
    def available(self) -> bool:
        return self.runtime.diagnostics_ok and self.runtime.diagnostics is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.runtime.async_add_diagnostics_listener(
                self._async_runtime_updated
            )
        )
