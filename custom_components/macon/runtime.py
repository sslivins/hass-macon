"""Per-config-entry runtime for one Macon heat pump controller."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util import dt as dt_util
from pymacon import (
    ClientStatus,
    ControllerCapabilities,
    ControllerDiagnostics,
    MaconAuthenticationError,
    MaconCertificateError,
    MaconClient,
    MaconControllerError,
    StateSnapshot,
)
from yarl import URL

from .const import (
    DIAGNOSTICS_INTERVAL,
    DOMAIN,
    EVENT_MACON_FAULT,
    SPLIT_HEAT_PUMP_IDENTIFIER_SUFFIX,
)

_LOGGER = logging.getLogger(__name__)

MANUFACTURER = "Macon"
DEFAULT_MODEL = "Heat Pump Controller"


class MaconRuntime:
    """Own one controller client and notify its Home Assistant entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MaconClient,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.snapshot: StateSnapshot | None = None
        self.status = ClientStatus(False, False, None)
        self._listeners: set[Callable[[], None]] = set()
        self._unsubscribe_snapshot: Callable[[], None] | None = None
        self._unsubscribe_status: Callable[[], None] | None = None
        self._unsubscribe_capabilities: Callable[[], None] | None = None
        self._reauth_started = False
        self._last_fault_active: bool | None = None
        self._last_fault_code: str | None = None
        # Controller health, polled on its own cadence. Kept on a separate
        # listener set so a diagnostics poll never rewrites heat-pump entities.
        self.diagnostics: ControllerDiagnostics | None = None
        self.diagnostics_ok = False
        self.boot_time: datetime | None = None
        self.diagnostics_fetched_at: datetime | None = None
        self._boot_time_boot_id: str | None = None
        self._diagnostics_listeners: set[Callable[[], None]] = set()
        self._diagnostics_refreshing = False
        self._diagnostics_requested_boot: str | None = None
        self._unsubscribe_diagnostics_timer: Callable[[], None] | None = None

    @property
    def available(self) -> bool:
        return self.status.available and self.snapshot is not None

    @property
    def device_id(self) -> str:
        return self.entry.data["device_id"]

    @property
    def device_identifier(self) -> tuple[str, str]:
        return (DOMAIN, self.device_id)

    @property
    def _split_heat_pump_identifier(self) -> tuple[str, str]:
        """Heat-pump device identifier used by the 0.8.0-0.8.3 device split."""
        return (DOMAIN, f"{self.device_id}{SPLIT_HEAT_PUMP_IDENTIFIER_SUFFIX}")

    @property
    def device_info(self) -> DeviceInfo:
        """The one device per config entry: the heat pump and its controller.

        Heat-pump readings and controls sit in the device's normal sections;
        controller health is categorised as diagnostic so it gets its own.
        """
        capabilities = self.client.capabilities
        return DeviceInfo(
            identifiers={self.device_identifier},
            name=self.entry.title,
            manufacturer=MANUFACTURER,
            model=(
                capabilities.model
                if capabilities is not None and capabilities.model
                else DEFAULT_MODEL
            ),
            sw_version=(
                capabilities.firmware_version
                if capabilities is not None
                else None
            ),
            # The web UI is HTTPS-only; plain HTTP serves a 404 on purpose.
            configuration_url=str(
                URL.build(scheme="https", host=self.entry.data[CONF_HOST])
            ),
        )

    @callback
    def _async_find_device(
        self, device_registry: dr.DeviceRegistry, identifier: tuple[str, str]
    ) -> dr.DeviceEntry | None:
        """Find this entry's device by identifier on any supported HA.

        HA 2026.8 added a per-entry lookup and deprecated ``async_get_device``
        (identifiers are no longer unique across entries); older supported
        releases only have ``async_get_device``.
        """
        by_identifier = getattr(
            device_registry, "async_get_device_by_identifier", None
        )
        if by_identifier is not None:
            return cast(
                "dr.DeviceEntry | None",
                by_identifier(identifier, self.entry.entry_id),
            )
        return device_registry.async_get_device(identifiers={identifier})

    @callback
    def async_register_devices(self) -> None:
        """Register the device, merging the short-lived two-device split.

        0.8.0-0.8.3 split each entry into a controller device (bare device id)
        and a heat-pump device (``<id>:heat_pump``). The heat-pump row is the
        original pre-split row, carrying the user's name, area, and dashboard
        references, so keep it: move the controller's entities onto it, drop
        the controller row, and re-key it back to the bare device id. Entity
        ids are left untouched.
        """
        device_registry = dr.async_get(self.hass)
        heat_pump = self._async_find_device(
            device_registry, self._split_heat_pump_identifier
        )
        if heat_pump is not None:
            _LOGGER.info(
                "Merging Macon controller and heat pump devices for %s",
                self.device_id,
            )
            controller = self._async_find_device(
                device_registry, self.device_identifier
            )
            if controller is not None:
                entity_registry = er.async_get(self.hass)
                for entity in er.async_entries_for_device(
                    entity_registry,
                    controller.id,
                    include_disabled_entities=True,
                ):
                    entity_registry.async_update_entity(
                        entity.entity_id, device_id=heat_pump.id
                    )
                device_registry.async_remove_device(controller.id)
            device_registry.async_update_device(
                heat_pump.id,
                new_identifiers={self.device_identifier},
                via_device_id=None,
            )
        device_registry.async_get_or_create(
            config_entry_id=self.entry.entry_id, **self.device_info
        )

    async def async_setup(self) -> None:
        self._unsubscribe_snapshot = self.client.subscribe(
            self._async_snapshot_received
        )
        self._unsubscribe_status = self.client.subscribe_status(
            self._async_status_received
        )
        self._unsubscribe_capabilities = self.client.subscribe_capabilities(
            self._async_capabilities_received
        )
        self.snapshot = await self.client.start()
        if self.snapshot is not None:
            # Seed the fault baseline from the initial snapshot so an already
            # active fault is not re-announced on startup, and the first
            # pushed transition fires an event.
            error = self.snapshot.state.error
            self._last_fault_active = error.active
            self._last_fault_code = error.code
        self.status = self.client.status

    @callback
    def async_start_diagnostics(self) -> None:
        """Poll controller health now and then every DIAGNOSTICS_INTERVAL."""
        self._unsubscribe_diagnostics_timer = async_track_time_interval(
            self.hass,
            self._async_diagnostics_tick,
            DIAGNOSTICS_INTERVAL,
            name=f"Macon diagnostics {self.device_id}",
            cancel_on_shutdown=True,
        )
        self._async_request_diagnostics_refresh()

    @callback
    def _async_diagnostics_tick(self, _now: datetime) -> None:
        self._async_request_diagnostics_refresh()

    @callback
    def _async_request_diagnostics_refresh(self) -> None:
        self.entry.async_create_task(
            self.hass,
            self.async_refresh_diagnostics(),
            f"Macon diagnostics refresh {self.device_id}",
        )

    async def async_refresh_diagnostics(self) -> None:
        capabilities = self.client.capabilities
        if capabilities is None or not capabilities.diagnostics:
            # Older firmware (or a rollback): only the controller-health
            # entities go unavailable; everything else keeps working.
            if self.diagnostics is not None or self.diagnostics_ok:
                self.diagnostics = None
                self.diagnostics_ok = False
                self._async_notify_diagnostics_listeners()
            return
        if self._diagnostics_refreshing:
            return
        self._diagnostics_refreshing = True
        try:
            diagnostics = await self.client.async_fetch_diagnostics()
        except MaconControllerError as error:
            if self.diagnostics_ok:
                _LOGGER.debug(
                    "Macon diagnostics poll for %s failed: %s",
                    self.device_id,
                    error,
                )
            self.diagnostics_ok = False
        else:
            self.diagnostics_fetched_at = dt_util.utcnow()
            self._async_track_boot_time(diagnostics)
            self.diagnostics = diagnostics
            self.diagnostics_ok = True
        finally:
            self._diagnostics_refreshing = False
        self._async_notify_diagnostics_listeners()

    @callback
    def _async_track_boot_time(self, diagnostics: ControllerDiagnostics) -> None:
        """Derive the boot timestamp once per boot so it doesn't jitter."""
        if diagnostics.boot_id == self._boot_time_boot_id:
            return
        if diagnostics.uptime_ms is None:
            self.boot_time = None
            return
        booted = dt_util.utcnow() - timedelta(milliseconds=diagnostics.uptime_ms)
        self.boot_time = booted.replace(microsecond=0)
        self._boot_time_boot_id = diagnostics.boot_id

    def controller_time(self, uptime_ms: int | None) -> datetime | None:
        """Convert a controller uptime (this boot) to a wall-clock time.

        Anchored to the poll that reported it rather than the frozen boot
        time, so clock drift between HA and the controller can't accumulate
        over a long uptime (or produce a time in the future).
        """
        diagnostics = self.diagnostics
        fetched_at = self.diagnostics_fetched_at
        if (
            uptime_ms is None
            or diagnostics is None
            or diagnostics.uptime_ms is None
            or fetched_at is None
        ):
            return None
        age_ms = max(0, diagnostics.uptime_ms - uptime_ms)
        return (fetched_at - timedelta(milliseconds=age_ms)).replace(
            microsecond=0
        )

    async def async_shutdown(self) -> None:
        if self._unsubscribe_diagnostics_timer is not None:
            self._unsubscribe_diagnostics_timer()
            self._unsubscribe_diagnostics_timer = None
        if self._unsubscribe_snapshot is not None:
            self._unsubscribe_snapshot()
            self._unsubscribe_snapshot = None
        if self._unsubscribe_status is not None:
            self._unsubscribe_status()
            self._unsubscribe_status = None
        if self._unsubscribe_capabilities is not None:
            self._unsubscribe_capabilities()
            self._unsubscribe_capabilities = None
        await self.client.stop()
        self._listeners.clear()
        self._diagnostics_listeners.clear()

    @callback
    def async_add_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    @callback
    def async_add_diagnostics_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        self._diagnostics_listeners.add(listener)

        @callback
        def unsubscribe() -> None:
            self._diagnostics_listeners.discard(listener)

        return unsubscribe

    @callback
    def _async_snapshot_received(self, snapshot: StateSnapshot) -> None:
        self.snapshot = snapshot
        self._async_fire_fault_transitions(snapshot)
        self._async_notify_listeners()
        # A new boot changes the reset reason, counters, and boot time; don't
        # leave them a whole poll interval stale.
        if (
            self.diagnostics is not None
            and snapshot.boot_id != self.diagnostics.boot_id
            and snapshot.boot_id != self._diagnostics_requested_boot
        ):
            self._diagnostics_requested_boot = snapshot.boot_id
            self._async_request_diagnostics_refresh()

    @callback
    def _async_fire_fault_transitions(
        self, snapshot: StateSnapshot
    ) -> None:
        error = snapshot.state.error
        if self._last_fault_active is None:
            # Establish a baseline on the first snapshot without firing,
            # so a fault already present at startup is not re-announced.
            self._last_fault_active = error.active
            self._last_fault_code = error.code
            return
        if (
            error.active == self._last_fault_active
            and error.code == self._last_fault_code
        ):
            return
        self._last_fault_active = error.active
        self._last_fault_code = error.code
        self.hass.bus.async_fire(
            EVENT_MACON_FAULT,
            {
                "device_id": self.device_id,
                "active": error.active,
                "code": error.code,
                "name": error.name,
                "description": error.description,
                "severity": error.severity,
            },
        )

    @callback
    def _async_status_received(self, status: ClientStatus) -> None:
        self.status = status
        if (
            isinstance(
                status.last_error,
                (MaconAuthenticationError, MaconCertificateError),
            )
            and not self._reauth_started
        ):
            self._reauth_started = True
            self.entry.async_start_reauth(self.hass)
        self._async_notify_listeners()

    @callback
    def _async_capabilities_received(
        self, capabilities: ControllerCapabilities
    ) -> None:
        self._async_update_registered_device(capabilities)
        self._async_notify_listeners()

    @callback
    def _async_update_registered_device(
        self, capabilities: ControllerCapabilities
    ) -> None:
        """Refresh device-registry identity from new capabilities.

        Home Assistant only reads an entity's ``device_info`` when the device
        is first registered; it is not re-read on subsequent state writes. So
        after an OTA the controller reports a new ``firmware_version`` in its
        capabilities, but the device registry (and the Device Info card) keeps
        showing the old ``sw_version`` until the entry is reloaded. Push the
        refreshed firmware version and model into the registry explicitly.
        """
        device_registry = dr.async_get(self.hass)
        device = self._async_find_device(
            device_registry, self.device_identifier
        )
        if device is None:
            return
        sw_version: str | UndefinedType = UNDEFINED
        new_sw = capabilities.firmware_version or None
        if new_sw is not None and device.sw_version != new_sw:
            sw_version = new_sw
        model: str | UndefinedType = UNDEFINED
        new_model = capabilities.model or None
        if new_model is not None and device.model != new_model:
            model = new_model
        if sw_version is not UNDEFINED or model is not UNDEFINED:
            device_registry.async_update_device(
                device.id, sw_version=sw_version, model=model
            )

    @callback
    def _async_notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    @callback
    def _async_notify_diagnostics_listeners(self) -> None:
        for listener in tuple(self._diagnostics_listeners):
            listener()
