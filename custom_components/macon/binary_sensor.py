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
from pymacon import ControllerDiagnostics, StateSnapshot

from .const import BUS_PROBLEM_CONSECUTIVE_FAILURES, TIME_SYNC_GRACE_MS
from .entity import (
    MaconControllerDiagnosticEntity,
    MaconControllerEntity,
    MaconEntity,
)
from .runtime import MaconRuntime


@dataclass(frozen=True, kw_only=True)
class MaconBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[StateSnapshot], bool]


@dataclass(frozen=True, kw_only=True)
class MaconControllerBinarySensorDescription(BinarySensorEntityDescription):
    """A controller-health binary sensor sourced from the diagnostics poll."""

    value_fn: Callable[[ControllerDiagnostics], bool | None]


def _bus_problem(diag: ControllerDiagnostics) -> bool | None:
    """RS485 link trouble the heat-pump entities can't show on their own."""
    if diag.bus_role == "blocked":
        # Another master is driving the bus, so this controller stood down.
        return True
    if diag.bus_role != "master":
        return False if diag.bus_role is not None else None
    if diag.bus_consecutive_failures is None:
        return None
    return diag.bus_consecutive_failures >= BUS_PROBLEM_CONSECUTIVE_FAILURES


def _time_sync_problem(diag: ControllerDiagnostics) -> bool | None:
    if diag.time_synced is None:
        return None
    if diag.time_synced:
        return False
    if diag.uptime_ms is None:
        return None
    return diag.uptime_ms >= TIME_SYNC_GRACE_MS


CONTROLLER_DESCRIPTIONS: tuple[MaconControllerBinarySensorDescription, ...] = (
    MaconControllerBinarySensorDescription(
        key="safe_mode",
        name="Safe mode",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda diag: diag.safe_mode,
    ),
    MaconControllerBinarySensorDescription(
        key="bus_problem",
        name="RS485 problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bus_problem,
    ),
    MaconControllerBinarySensorDescription(
        key="time_sync_problem",
        name="Time sync problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_time_sync_problem,
    ),
    MaconControllerBinarySensorDescription(
        key="ota_pending_verify",
        name="Firmware pending verification",
        entity_registry_enabled_default=False,
        value_fn=lambda diag: diag.ota_pending_verify,
    ),
)


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
    entities: list[BinarySensorEntity] = [
        MaconBinarySensor(runtime, description)
        for description in DESCRIPTIONS
    ]
    entities.append(MaconPushConnectedSensor(runtime))
    entities.extend(
        MaconControllerBinarySensor(runtime, description)
        for description in CONTROLLER_DESCRIPTIONS
    )
    async_add_entities(entities)


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


class MaconPushConnectedSensor(MaconControllerEntity, BinarySensorEntity):
    """Whether Home Assistant has a live push stream to the controller.

    Off means updates are arriving by the slower fallback poll (or not at all).
    """

    _attr_name = "Push connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: MaconRuntime) -> None:
        super().__init__(runtime, "push_connected")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.runtime.status.stream_connected


class MaconControllerBinarySensor(
    MaconControllerDiagnosticEntity, BinarySensorEntity
):
    entity_description: MaconControllerBinarySensorDescription

    def __init__(
        self,
        runtime: MaconRuntime,
        description: MaconControllerBinarySensorDescription,
    ) -> None:
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        diagnostics = self.diagnostics
        if diagnostics is None:
            return None
        return self.entity_description.value_fn(diagnostics)
