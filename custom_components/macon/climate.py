"""Climate entity for power, HVAC display, and advertised setpoints."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymacon import ControllerState

from .const import HEATING_MODES, normalize_mode, setpoint_kind
from .entity import MaconEntity
from .runtime import MaconRuntime

MODE_MAP = {
    "cooling": HVACMode.COOL,
    "heating": HVACMode.HEAT,
    "mode_2": HVACMode.HEAT,
    "mode_3": HVACMode.HEAT,
    "mode_4": HVACMode.HEAT,
    "hot_water": HVACMode.HEAT,
    "hot_water_cooling": HVACMode.HEAT_COOL,
}

ACTION_MAP = {
    "off": HVACAction.OFF,
    "idle": HVACAction.IDLE,
    "heating": HVACAction.HEATING,
    "cooling": HVACAction.COOLING,
    "defrost": HVACAction.DEFROSTING,
    "fault": HVACAction.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MaconClimate(entry.runtime_data)])


class MaconClimate(MaconEntity, ClimateEntity):
    """Expose requested mode separately from actual heat-pump operation."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, runtime: MaconRuntime) -> None:
        super().__init__(runtime, "climate")

    @property
    def current_temperature(self) -> float | None:
        state = self._state
        return None if state is None else state.temperatures_c.tank

    @property
    def target_temperature(self) -> float | None:
        state = self._state
        kind = self._setpoint_kind
        if state is None or kind is None:
            return None
        return getattr(state.setpoints_c, kind)

    @property
    def min_temp(self) -> float:
        limits = self._limits
        return 0 if limits is None else limits.minimum

    @property
    def max_temp(self) -> float:
        limits = self._limits
        return 0 if limits is None else limits.maximum

    @property
    def hvac_modes(self) -> list[HVACMode]:
        capabilities = self.runtime.client.capabilities
        modes = [HVACMode.OFF]
        state = self._state
        if capabilities is not None and capabilities.control_power:
            supported = {normalize_mode(m) for m in capabilities.supported_modes}
            if "cooling" in supported:
                modes.append(HVACMode.COOL)
            if "hot_water_cooling" in supported:
                modes.append(HVACMode.HEAT_COOL)
            if supported & (HEATING_MODES | {"hot_water"}):
                modes.append(HVACMode.HEAT)
        if state is not None:
            current_mode = MODE_MAP.get(normalize_mode(state.mode))
            if current_mode is not None and current_mode not in modes:
                modes.append(current_mode)
        return modes

    @property
    def supported_features(self) -> ClimateEntityFeature:
        capabilities = self.runtime.client.capabilities
        kind = self._setpoint_kind
        if capabilities is None or kind is None:
            return ClimateEntityFeature(0)
        if getattr(capabilities.setpoint_controls, kind):
            return ClimateEntityFeature.TARGET_TEMPERATURE
        return ClimateEntityFeature(0)

    @property
    def hvac_mode(self) -> HVACMode | None:
        state = self._state
        if state is None:
            return None
        if not state.unit_on:
            return HVACMode.OFF
        return MODE_MAP.get(normalize_mode(state.mode), HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction | None:
        state = self._state
        if state is None or not state.connected:
            return None
        return ACTION_MAP.get(state.operation, HVACAction.IDLE)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        capabilities = self.runtime.client.capabilities
        if capabilities is None or not capabilities.control_power:
            raise HomeAssistantError("Power control is unavailable")
        if hvac_mode == HVACMode.OFF:
            await self.runtime.client.async_set_power(False)
            return

        if hvac_mode == HVACMode.HEAT:
            state = self._state
            if state is not None and normalize_mode(state.mode) in (
                HEATING_MODES | {"hot_water"}
            ):
                await self.runtime.client.async_set_power(True)
                return
            raise HomeAssistantError(
                "Select heating or hot water from the mode entity before "
                "turning heat on"
            )

        wanted = {
            HVACMode.COOL: "cooling",
            HVACMode.HEAT_COOL: "hot_water_cooling",
        }.get(hvac_mode)
        if wanted is None:
            raise HomeAssistantError(
                "Select an exact Macon mode from the mode entity"
            )
        # Send the key the controller advertised (older firmware says "auto").
        key = next(
            (
                m
                for m in capabilities.supported_modes
                if normalize_mode(m) == wanted
            ),
            None,
        )
        if not capabilities.control_mode or key is None:
            raise HomeAssistantError("Selected-mode control is unavailable")
        await self.runtime.client.async_set_mode(key)
        await self.runtime.client.async_set_power(True)

    async def async_set_temperature(self, **kwargs: float) -> None:
        value = kwargs.get(ATTR_TEMPERATURE)
        if value is None or isinstance(value, bool) or int(value) != value:
            raise HomeAssistantError("Macon setpoints require whole degrees C")
        capabilities = self.runtime.client.capabilities
        kind = self._setpoint_kind
        if capabilities is None or kind is None:
            raise HomeAssistantError("Setpoint control is unavailable")
        if not getattr(capabilities.setpoint_controls, kind):
            raise HomeAssistantError(
                f"{kind.replace('_', ' ').capitalize()} setpoint control "
                "is unavailable"
            )
        setter = {
            "cooling": self.runtime.client.async_set_cooling_setpoint,
            "heating": self.runtime.client.async_set_heating_setpoint,
            "hot_water": self.runtime.client.async_set_hot_water_setpoint,
        }[kind]
        await setter(int(value))

    @property
    def _setpoint_kind(self) -> str | None:
        state = self._state
        if state is None:
            return None
        return setpoint_kind(state.mode, state.operation)

    @property
    def _limits(self):
        capabilities = self.runtime.client.capabilities
        kind = self._setpoint_kind
        if capabilities is None or kind is None:
            return None
        return getattr(capabilities, f"{kind}_range")

    @property
    def _state(self) -> ControllerState | None:
        snapshot = self.runtime.snapshot
        return None if snapshot is None else snapshot.state
