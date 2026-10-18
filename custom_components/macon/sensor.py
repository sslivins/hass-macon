"""Read-only sensor entities for the Macon heat pump controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from pymacon import (
    ControllerCapabilities,
    ControllerDiagnostics,
    EnergyTotals,
    StateSnapshot,
)

from .const import (
    BUS_ROLES,
    COP_SOURCES,
    DOMAIN,
    FAULT_CODES,
    FAULT_STATE_OK,
    FAULT_STATE_UNKNOWN,
    RESET_REASONS,
    STATE_UNKNOWN_ENUM,
    WORKING_MODES,
    normalize_mode,
    setpoint_kind,
)
from .entity import (
    MaconControllerDiagnosticEntity,
    MaconControllerEntity,
    MaconEntity,
)
from .runtime import MaconRuntime


@dataclass(frozen=True, kw_only=True)
class MaconSensorDescription(SensorEntityDescription):
    value_fn: Callable[[StateSnapshot], str | int | float | None]
    attributes_fn: (
        Callable[[StateSnapshot], dict[str, str | None]] | None
    ) = None


@dataclass(frozen=True, kw_only=True)
class MaconInfoSensorDescription(SensorEntityDescription):
    """A diagnostic sensor sourced from the controller capabilities document."""

    value_fn: Callable[[ControllerCapabilities | None], str | None]


@dataclass(frozen=True, kw_only=True)
class MaconControllerSensorDescription(SensorEntityDescription):
    """A controller-health sensor sourced from the diagnostics poll."""

    value_fn: Callable[
        [ControllerDiagnostics, MaconRuntime],
        str | int | float | datetime | None,
    ]


def _enum(value: str | None, options: tuple[str, ...]) -> str | None:
    if value is None:
        return None
    return value if value in options else STATE_UNKNOWN_ENUM


def _fault_state(snapshot: StateSnapshot) -> str:
    error = snapshot.state.error
    if not error.active:
        return FAULT_STATE_OK
    if error.code and error.code in FAULT_CODES:
        return error.code
    return FAULT_STATE_UNKNOWN


def _active_setpoint(snapshot: StateSnapshot) -> float | None:
    """The setpoint the unit is working to in its selected mode."""
    state = snapshot.state
    kind = setpoint_kind(state.mode, state.operation)
    return None if kind is None else getattr(state.setpoints_c, kind)


def _trend(snapshot: StateSnapshot, key: str) -> dict[str, str | None]:
    """Direction of a water temperature: rising, falling, steady or None.

    None while the controller has too few readings, or on firmware before
    3.2.8, which doesn't report trends.
    """
    trends = snapshot.state.trends
    return {"trend": getattr(trends, key) if trends is not None else None}


def _cop_source(snapshot: StateSnapshot) -> str | None:
    """Where the COP's water temperatures come from."""
    readings = snapshot.state.readings
    if readings.perf_fallback:
        return "fallback"
    return _enum(readings.perf_source, COP_SOURCES)


TEMPERATURES: tuple[MaconSensorDescription, ...] = (
    MaconSensorDescription(
        key="tank_temperature",
        name="Tank temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.tank,
        attributes_fn=lambda value: _trend(value, "tank"),
    ),
    MaconSensorDescription(
        key="outlet_temperature",
        name="Outlet temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.outlet,
        attributes_fn=lambda value: _trend(value, "outlet"),
    ),
    MaconSensorDescription(
        key="inlet_temperature",
        name="Inlet temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.inlet,
        attributes_fn=lambda value: _trend(value, "inlet"),
    ),
    MaconSensorDescription(
        key="outdoor_temperature",
        name="Outdoor temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.outdoor_ambient,
    ),
)

SETPOINTS: tuple[MaconSensorDescription, ...] = (
    MaconSensorDescription(
        key="active_setpoint",
        name="Active setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_active_setpoint,
    ),
    MaconSensorDescription(
        key="cooling_setpoint",
        name="Cooling setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda value: value.state.setpoints_c.cooling,
    ),
    MaconSensorDescription(
        key="heating_setpoint",
        name="Heating setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda value: value.state.setpoints_c.heating,
    ),
    MaconSensorDescription(
        key="hot_water_setpoint",
        name="Hot water setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda value: value.state.setpoints_c.hot_water,
    ),
)

READINGS: tuple[MaconSensorDescription, ...] = (
    MaconSensorDescription(
        key="working_mode",
        name="Working mode",
        device_class=SensorDeviceClass.ENUM,
        options=[*WORKING_MODES, STATE_UNKNOWN_ENUM],
        value_fn=lambda value: _enum(
            normalize_mode(value.state.mode), WORKING_MODES
        ),
    ),
    MaconSensorDescription(
        key="operation",
        name="Operation",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "idle",
            "heating",
            "cooling",
            "defrost",
            "fault",
            "unknown",
        ],
        value_fn=lambda value: value.state.operation,
    ),
    MaconSensorDescription(
        key="compressor_frequency",
        name="Compressor frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: (
            value.state.readings.compressor_frequency_hz
        ),
    ),
    MaconSensorDescription(
        key="fan_speed",
        name="Fan speed",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.fan_rpm,
    ),
    # Expansion valve position, in raw steps.
    #
    # The controller sends null (not 0) when the register has not been read,
    # because 0 steps means the valve is fully CLOSED, a real and alarming
    # state. value_fn passes None straight through so the entity reports
    # `unknown` instead of a fabricated 0.
    #
    # No device_class: Home Assistant has no valve-position/step class. No
    # percentage either, because the mainboard publishes no full-scale step
    # count, so a percentage could only ever be a guess.
    #
    # The `name` slug is a contract with macon-heat-pump-card, which resolves
    # entities with entityId.endsWith("_" + suffix). This must keep producing
    # sensor.<device>_expansion_valve_position.
    MaconSensorDescription(
        key="expansion_valve_position",
        name="Expansion valve position",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.primary_eev,
    ),
    # Electrical readings follow the same null-means-unknown rule.
    MaconSensorDescription(
        key="ac_voltage",
        name="AC voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.ac_voltage,
    ),
    MaconSensorDescription(
        key="ac_current",
        name="AC current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.ac_current,
    ),
    MaconSensorDescription(
        key="dc_voltage",
        name="DC bus voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.dc_voltage,
    ),
    MaconSensorDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.power_w,
    ),
    MaconSensorDescription(
        key="thermal_output",
        name="Thermal output",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.thermal_w,
    ),
    MaconSensorDescription(
        key="cop",
        name="Coefficient of performance",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.readings.cop,
    ),
    # Performance inputs, as configured on the controller. Diagnostic: they
    # explain the COP rather than being readings in their own right. Older
    # firmware doesn't send them, so they report unknown there.
    MaconSensorDescription(
        key="loop_flow",
        name="Loop flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value.state.readings.flow_lpm,
    ),
    MaconSensorDescription(
        key="cop_source",
        translation_key="cop_source",
        name="COP source",
        device_class=SensorDeviceClass.ENUM,
        options=[*COP_SOURCES, "fallback", STATE_UNKNOWN_ENUM],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_cop_source,
    ),
    MaconSensorDescription(
        key="fan_level",
        name="Fan level",
        value_fn=lambda value: value.state.components.fan_level,
    ),
    MaconSensorDescription(
        key="fault_code",
        name="Fault code",
        device_class=SensorDeviceClass.ENUM,
        options=[*FAULT_CODES, FAULT_STATE_UNKNOWN, FAULT_STATE_OK],
        value_fn=_fault_state,
        attributes_fn=lambda value: {
            "description": value.state.error.description,
            "help_url": value.state.error.help_url,
        },
    ),
)

EXTRA_TEMPERATURES: tuple[MaconSensorDescription, ...] = tuple(
    MaconSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
    )
    for key, name, value_fn in (
        (
            "discharge_temperature",
            "Discharge temperature",
            lambda value: value.state.temperatures_c.discharge,
        ),
        (
            "suction_temperature",
            "Suction temperature",
            lambda value: value.state.temperatures_c.suction,
        ),
        (
            "outdoor_coil_temperature",
            "Outdoor coil temperature",
            lambda value: value.state.temperatures_c.outdoor_coil,
        ),
        (
            "indoor_coil_temperature",
            "Indoor coil temperature",
            lambda value: value.state.temperatures_c.indoor_coil,
        ),
        (
            "ipm_temperature",
            "IPM temperature",
            lambda value: value.state.temperatures_c.ipm,
        ),
    )
)

DESCRIPTIONS = TEMPERATURES + SETPOINTS + READINGS + EXTRA_TEMPERATURES


@dataclass(frozen=True, kw_only=True)
class MaconEnergySensorDescription(SensorEntityDescription):
    value_fn: Callable[[EnergyTotals], int]


def _energy(
    key: str, name: str, value_fn: Callable[[EnergyTotals], int]
) -> MaconEnergySensorDescription:
    return MaconEnergySensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=value_fn,
    )


# Lifetime meters kept by the controller (firmware 3.4.0+), for the Energy
# dashboard. Heat delivered in each mode is heat moved into (or, for cooling,
# out of) the water.
ENERGY_SENSORS: tuple[MaconEnergySensorDescription, ...] = (
    _energy("electrical_energy", "Electrical energy", lambda e: e.electrical_wh),
    _energy("heating_energy", "Heating energy", lambda e: e.heating_wh),
    _energy("cooling_energy", "Cooling energy", lambda e: e.cooling_wh),
    _energy("hot_water_energy", "Hot water energy", lambda e: e.hot_water_wh),
)

INFO_SENSORS: tuple[MaconInfoSensorDescription, ...] = (
    MaconInfoSensorDescription(
        key="ip_address",
        name="IP address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda caps: caps.ip_address if caps else None,
    ),
    MaconInfoSensorDescription(
        key="hostname",
        name="Hostname",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda caps: caps.local_hostname if caps else None,
    ),
)


def _count(
    key: str,
    name: str,
    value_fn: Callable[[ControllerDiagnostics], int | None],
    *,
    enabled: bool = False,
) -> MaconControllerSensorDescription:
    return MaconControllerSensorDescription(
        key=key,
        name=name,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=enabled,
        value_fn=lambda diag, _runtime: value_fn(diag),
    )


def _bytes(
    key: str,
    name: str,
    value_fn: Callable[[ControllerDiagnostics], int | None],
) -> MaconControllerSensorDescription:
    return MaconControllerSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda diag, _runtime: value_fn(diag),
    )


# Lifetime counters (brownout, panic, watchdog) survive reboots on the
# controller. RS485 and Wi-Fi counters are per boot; TOTAL_INCREASING treats
# the drop back to zero after a reboot as a counter reset.
CONTROLLER_SENSORS: tuple[MaconControllerSensorDescription, ...] = (
    MaconControllerSensorDescription(
        key="last_boot",
        name="Last boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda _diag, runtime: runtime.boot_time,
    ),
    MaconControllerSensorDescription(
        key="last_reset_reason",
        name="Last reset reason",
        device_class=SensorDeviceClass.ENUM,
        options=[*RESET_REASONS, STATE_UNKNOWN_ENUM],
        value_fn=lambda diag, _runtime: _enum(
            diag.last_reset_reason, RESET_REASONS
        ),
    ),
    _count(
        "brownout_count",
        "Brownout count",
        lambda diag: diag.brownout_count,
        enabled=True,
    ),
    _count(
        "panic_count",
        "Crash count",
        lambda diag: diag.panic_count,
        enabled=True,
    ),
    _count(
        "watchdog_count",
        "Watchdog reset count",
        lambda diag: diag.watchdog_count,
        enabled=True,
    ),
    MaconControllerSensorDescription(
        key="bus_role",
        name="RS485 role",
        device_class=SensorDeviceClass.ENUM,
        options=[*BUS_ROLES, STATE_UNKNOWN_ENUM],
        value_fn=lambda diag, _runtime: _enum(diag.bus_role, BUS_ROLES),
    ),
    MaconControllerSensorDescription(
        key="bus_consecutive_failures",
        name="RS485 consecutive failures",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda diag, _runtime: diag.bus_consecutive_failures,
    ),
    _count(
        "wifi_disconnect_count",
        "Wi-Fi disconnects",
        lambda diag: diag.wifi_disconnect_count,
        enabled=True,
    ),
    # Drops the controller counted since boot: short ones reconnected within a
    # minute, long ones were reported as a Wi-Fi outage.
    _count(
        "wifi_drops_short",
        "Wi-Fi short drops",
        lambda diag: diag.wifi_drops_short,
        enabled=True,
    ),
    _count(
        "wifi_drops_long",
        "Wi-Fi long drops",
        lambda diag: diag.wifi_drops_long,
        enabled=True,
    ),
    MaconControllerSensorDescription(
        key="wifi_rssi",
        name="Wi-Fi signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda diag, _runtime: diag.wifi_rssi_dbm,
    ),
    MaconControllerSensorDescription(
        key="wifi_ssid",
        name="Wi-Fi network",
        entity_registry_enabled_default=False,
        value_fn=lambda diag, _runtime: diag.wifi_ssid,
    ),
    MaconControllerSensorDescription(
        key="wifi_last_disconnect_reason",
        name="Wi-Fi last disconnect reason",
        entity_registry_enabled_default=False,
        value_fn=lambda diag, _runtime: diag.wifi_last_disconnect_reason,
    ),
    _bytes(
        "internal_free_memory",
        "Free internal memory",
        lambda diag: diag.internal_free_bytes,
    ),
    _bytes(
        "internal_min_free_memory",
        "Minimum free internal memory",
        lambda diag: diag.internal_min_free_bytes,
    ),
    _bytes(
        "internal_largest_free_block",
        "Largest free internal block",
        lambda diag: diag.internal_largest_free_block_bytes,
    ),
    _count("bus_polls_ok", "RS485 polls OK", lambda diag: diag.bus_polls_ok),
    _count(
        "bus_polls_no_response",
        "RS485 polls without response",
        lambda diag: diag.bus_polls_no_response,
    ),
    _count(
        "bus_polls_transport_error",
        "RS485 transport errors",
        lambda diag: diag.bus_polls_transport_error,
    ),
    _count(
        "bus_checksum_errors",
        "RS485 checksum errors",
        lambda diag: diag.bus_checksum_errors,
    ),
    _count(
        "bus_writes_ok", "RS485 writes OK", lambda diag: diag.bus_writes_ok
    ),
    _count(
        "bus_writes_failed",
        "RS485 writes failed",
        lambda diag: diag.bus_writes_failed,
    ),
    _count(
        "bus_frames_ok",
        "RS485 frames received",
        lambda diag: diag.bus_frames_ok,
    ),
    _count("bus_resyncs", "RS485 resyncs", lambda diag: diag.bus_resyncs),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: MaconRuntime = entry.runtime_data
    _remove_retired_sensors(hass, runtime)
    entities: list[SensorEntity] = [
        MaconSensor(runtime, description) for description in DESCRIPTIONS
    ]
    entities.extend(
        MaconEnergySensor(runtime, description) for description in ENERGY_SENSORS
    )
    entities.extend(
        MaconInfoSensor(runtime, description)
        for description in INFO_SENSORS
    )
    entities.extend(
        MaconControllerSensor(runtime, description)
        for description in CONTROLLER_SENSORS
    )
    async_add_entities(entities)


# Sensors that no longer exist. Remove them so they don't linger as
# "unavailable" on the device page.
# - bus_last_ok: now the last_response attribute of RS485 problem, since a
#   timestamp that changes every poll flooded the logbook.
RETIRED_SENSOR_KEYS = ("bus_last_ok",)


def _remove_retired_sensors(hass: HomeAssistant, runtime: MaconRuntime) -> None:
    registry = er.async_get(hass)
    for key in RETIRED_SENSOR_KEYS:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{runtime.device_id}_{key}"
        )
        if entity_id:
            registry.async_remove(entity_id)


class MaconSensor(MaconEntity, SensorEntity):
    entity_description: MaconSensorDescription

    def __init__(
        self,
        runtime: MaconRuntime,
        description: MaconSensorDescription,
    ) -> None:
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        snapshot = self.runtime.snapshot
        if snapshot is None:
            return None
        return self.entity_description.value_fn(snapshot)

    @property
    def extra_state_attributes(self) -> dict[str, str | None] | None:
        attributes_fn = self.entity_description.attributes_fn
        if attributes_fn is None:
            return None
        snapshot = self.runtime.snapshot
        if snapshot is None:
            return None
        return attributes_fn(snapshot)


@dataclass
class _EnergyRestoreData(ExtraStoredData):
    reset_id: str | None
    wh: int

    def as_dict(self) -> dict[str, Any]:
        return {"reset_id": self.reset_id, "wh": self.wh}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _EnergyRestoreData | None:
        reset_id = data.get("reset_id")
        wh = data.get("wh")
        if reset_id is not None and not isinstance(reset_id, str):
            return None
        if isinstance(wh, bool) or not isinstance(wh, int) or wh < 0:
            return None
        return cls(reset_id, wh)


class MaconEnergySensor(MaconEntity, SensorEntity, RestoreEntity):
    """Lifetime energy meter that never runs backwards by accident.

    The controller saves today's running total every few minutes, so a reboot
    can hand back a slightly smaller figure. A long-term statistics meter would
    read that dip as a reset and double-count, so the last value is held until
    the controller catches up. A different reset_id means the controller's
    history really was wiped, and the meter is allowed to start again. A
    reset_id appearing for the first time is the same meter (the controller
    only assigns one once its first day is saved).
    """

    entity_description: MaconEnergySensorDescription

    def __init__(
        self,
        runtime: MaconRuntime,
        description: MaconEnergySensorDescription,
    ) -> None:
        super().__init__(runtime, description.key)
        self.entity_description = description
        self._reset_id: str | None = None
        self._wh: int | None = None
        self._reporting = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        extra = await self.async_get_last_extra_data()
        if extra is not None:
            restored = _EnergyRestoreData.from_dict(extra.as_dict())
            if restored is not None:
                self._reset_id = restored.reset_id
                self._wh = restored.wh
        self._track()

    def _async_runtime_updated(self) -> None:
        self._track()
        super()._async_runtime_updated()

    def _track(self) -> None:
        snapshot = self.runtime.snapshot
        energy = snapshot.state.energy if snapshot is not None else None
        # Older firmware, or the controller hasn't loaded its history yet.
        self._reporting = energy is not None
        if energy is None:
            return
        wh = self.entity_description.value_fn(energy)
        same_meter = self._reset_id is None or energy.reset_id == self._reset_id
        if same_meter and self._wh is not None:
            wh = max(wh, self._wh)
        self._wh = wh
        self._reset_id = energy.reset_id

    @property
    def native_value(self) -> int | None:
        return self._wh if self._reporting else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"reset_id": self._reset_id}

    @property
    def extra_restore_state_data(self) -> _EnergyRestoreData | None:
        if self._wh is None:
            return None
        return _EnergyRestoreData(self._reset_id, self._wh)


class MaconInfoSensor(MaconControllerEntity, SensorEntity):
    """Diagnostic sensor sourced from the controller capabilities document."""

    entity_description: MaconInfoSensorDescription

    def __init__(
        self,
        runtime: MaconRuntime,
        description: MaconInfoSensorDescription,
    ) -> None:
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        # Network identity comes from capabilities, which are cached across
        # brief stream drops, so keep it visible whenever it is known.
        return self.runtime.client.capabilities is not None

    @property
    def native_value(self) -> str | None:
        return self.entity_description.value_fn(
            self.runtime.client.capabilities
        )


class MaconControllerSensor(MaconControllerDiagnosticEntity, SensorEntity):
    """Controller-health sensor sourced from the diagnostics poll."""

    entity_description: MaconControllerSensorDescription

    def __init__(
        self,
        runtime: MaconRuntime,
        description: MaconControllerSensorDescription,
    ) -> None:
        super().__init__(runtime, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        diagnostics = self.diagnostics
        if diagnostics is None:
            return None
        return self.entity_description.value_fn(diagnostics, self.runtime)
