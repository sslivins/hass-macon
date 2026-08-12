"""Read-only binary sensors for the Macon heat pump controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymacon import StateSnapshot

from .entity import MaconEntity
from .runtime import MaconRuntime


@dataclass(frozen=True, kw_only=True)
class MaconBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[StateSnapshot], bool]


DESCRIPTIONS: tuple[MaconBinarySensorDescription, ...] = (
    MaconBinarySensorDescription(
        key="heat_pump_connected",
        name="Heat pump connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda value: value.state.connected,
    ),
    MaconBinarySensorDescription(
        key="unit_power",
        name="Unit power",
        value_fn=lambda value: value.state.unit_on,
    ),
    MaconBinarySensorDescription(
        key="defrosting",
        name="Defrosting",
        value_fn=lambda value: value.state.defrosting,
    ),
    MaconBinarySensorDescription(
        key="active_error",
        name="Active error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda value: value.state.error.active,
    ),
    MaconBinarySensorDescription(
        key="compressor",
        name="Compressor",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda value: value.state.components.compressor,
    ),
    MaconBinarySensorDescription(
        key="fan",
        name="Fan",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda value: value.state.components.fan,
    ),
    MaconBinarySensorDescription(
        key="water_pump",
        name="Water pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda value: value.state.components.water_pump,
    ),
    MaconBinarySensorDescription(
        key="backup_heater",
        name="Backup heater",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda value: value.state.components.backup_heater,
    ),
    MaconBinarySensorDescription(
        key="reversing_valve_request",
        name="Reversing valve request",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda value: (
            value.state.components.reversing_valve_request
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: MaconRuntime = entry.runtime_data
    async_add_entities(
        MaconBinarySensor(runtime, description)
        for description in DESCRIPTIONS
    )


class MaconBinarySensor(MaconEntity, BinarySensorEntity):
    entity_description: MaconBinarySensorDescription

    def __init__(
        self,
        runtime: MaconRuntime,
        description: MaconBinarySensorDescription,
    ) -> None:
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        snapshot = self.runtime.snapshot
        if snapshot is None:
            return None
        return self.entity_description.value_fn(snapshot)
