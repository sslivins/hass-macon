"""Restart button for the Arctic controller."""

from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymacon import (
    MaconCommandConflictError,
    MaconControllerError,
    MaconControlUnavailableError,
)

from .entity import MaconControllerEntity
from .runtime import MaconRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MaconRestartButton(entry.runtime_data)])


class MaconRestartButton(MaconControllerEntity, ButtonEntity):
    """Reboot the controller (not the heat pump).

    Disabled by default: a restart drops RS485 control of the heat pump for
    the few seconds the controller takes to boot.
    """

    _attr_name = "Restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime: MaconRuntime) -> None:
        super().__init__(runtime, "restart")

    @property
    def available(self) -> bool:
        capabilities = self.runtime.client.capabilities
        return (
            super().available
            and capabilities is not None
            and capabilities.restart
        )

    async def async_press(self) -> None:
        snapshot = self.runtime.snapshot
        if snapshot is None:
            raise HomeAssistantError("The controller state is not known yet")
        try:
            await self.runtime.client.async_restart(boot_id=snapshot.boot_id)
        except MaconControlUnavailableError as error:
            raise HomeAssistantError(
                "The controller can't restart while a firmware update is "
                "in progress or awaiting verification"
            ) from error
        except MaconCommandConflictError as error:
            raise HomeAssistantError(
                "The controller has already restarted"
            ) from error
        except MaconControllerError as error:
            raise HomeAssistantError(
                f"Failed to restart the controller: {error}"
            ) from error
