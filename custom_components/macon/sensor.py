"""Read-only sensor entities for the Macon heat pump controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymacon import ControllerCapabilities, StateSnapshot

from .const import FAULT_CODES, FAULT_STATE_OK, FAULT_STATE_UNKNOWN
from .entity import MaconEntity
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


def _fault_state(snapshot: StateSnapshot) -> str:
    error = snapshot.state.error
    if not error.active:
        return FAULT_STATE_OK
    if error.code and error.code in FAULT_CODES:
        return error.code
    return FAULT_STATE_UNKNOWN


TEMPERATURES: tuple[MaconSensorDescription, ...] = (
    MaconSensorDescription(
        key="tank_temperature",
        name="Tank temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.tank,
    ),
    MaconSensorDescription(
        key="outlet_temperature",
        name="Outlet temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.outlet,
    ),
    MaconSensorDescription(
        key="inlet_temperature",
        name="Inlet temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda value: value.state.temperatures_c.inlet,
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

DIAGNOSTICS: tuple[MaconSensorDescription, ...] = (
    MaconSensorDescription(
        key="working_mode",
        name="Working mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "cooling",
            "floor_heating",
            "fan_coil_heating",
            "heating",
            "hot_water",
            "auto",
            "unknown",
        ],
        value_fn=lambda value: value.state.mode,
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
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: (
            value.state.readings.compressor_frequency_hz
        ),
    ),
    MaconSensorDescription(
        key="fan_speed",
        name="Fan speed",
        native_unit_of_measurement="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: value.state.readings.fan_rpm,
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
    MaconSensorDescription(
        key="fan_level",
        name="Fan level",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_category=EntityCategory.DIAGNOSTIC,
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

DESCRIPTIONS = TEMPERATURES + SETPOINTS + DIAGNOSTICS + EXTRA_TEMPERATURES

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: MaconRuntime = entry.runtime_data
    entities: list[SensorEntity] = [
        MaconSensor(runtime, description) for description in DESCRIPTIONS
    ]
    entities.extend(
        MaconInfoSensor(runtime, description)
        for description in INFO_SENSORS
    )
    async_add_entities(entities)


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


class MaconInfoSensor(MaconEntity, SensorEntity):
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
