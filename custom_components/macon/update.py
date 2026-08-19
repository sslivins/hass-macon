"""Firmware update entity for one Macon heat pump controller.

Surfaces the controller's OTA REST API (check GitHub, install, poll progress)
as a Home Assistant :class:`UpdateEntity`, giving the standard installed-vs-
latest display, an Install button, a live progress bar, and release notes.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymacon import (
    MaconCommandConflictError,
    MaconControllerError,
    OtaReleaseInfo,
)

from .entity import MaconEntity
from .runtime import MaconRuntime

_LOGGER = logging.getLogger(__name__)

# Checking for updates asks the controller to hit its release source (GitHub)
# live, so poll conservatively; an install drives its own faster progress loop.
SCAN_INTERVAL = timedelta(hours=6)

# Progress-loop tuning for an in-flight install.
_PROGRESS_POLL_SECONDS = 3.0
_INSTALL_TIMEOUT_SECONDS = 600.0
# Consecutive unreachable polls (after we've started) that we treat as the
# device having quiesced its network to flash and reboot, i.e. success.
_REBOOT_CONFIRM_POLLS = 5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MaconFirmwareUpdate(entry.runtime_data)])


class MaconFirmwareUpdate(MaconEntity, UpdateEntity):
    """Expose the controller's firmware OTA flow as an HA update entity."""

    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_should_poll = True
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(self, runtime: MaconRuntime) -> None:
        super().__init__(runtime, "firmware_update")
        self._release: OtaReleaseInfo | None = None

    @property
    def installed_version(self) -> str | None:
        capabilities = self.runtime.client.capabilities
        if capabilities is not None and capabilities.firmware_version:
            return capabilities.firmware_version
        if self._release is not None:
            return self._release.current_version
        return None

    @property
    def latest_version(self) -> str | None:
        if (
            self._release is not None
            and self._release.update_available
            and self._release.latest_version is not None
        ):
            return self._release.latest_version
        # No newer version known -> report installed so HA shows "up to date".
        return self.installed_version

    def release_notes(self) -> str | None:
        if self._release is not None and self._release.release_notes:
            return self._release.release_notes
        return None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Populate the badge promptly instead of waiting a whole scan interval.
        self.hass.async_create_task(self._async_initial_refresh())

    async def _async_initial_refresh(self) -> None:
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Refresh available-release info (skipped while installing)."""
        if self._attr_in_progress:
            return
        try:
            self._release = await self.runtime.client.async_check_updates()
        except MaconControllerError as error:
            # An update check failing (offline, GitHub hiccup) should not make
            # the whole entity unavailable; keep the last known release info.
            _LOGGER.debug("Macon update check failed: %s", error)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Download and install the latest firmware, reporting live progress."""
        if self._release is None or not self._release.update_available:
            # The badge may be stale; do a fresh check before giving up.
            await self.async_update()
        if (
            self._release is None
            or not self._release.update_available
            or not self._release.download_ready
        ):
            raise HomeAssistantError(
                "No firmware update is available to install"
            )

        self._attr_in_progress = True
        self._attr_update_percentage = 0
        self.async_write_ha_state()
        try:
            try:
                await self.runtime.client.async_start_update()
            except MaconCommandConflictError as error:
                raise HomeAssistantError(
                    "A firmware update is already in progress"
                ) from error
            except MaconControllerError as error:
                raise HomeAssistantError(
                    f"Failed to start firmware update: {error}"
                ) from error
            await self._await_completion()
        finally:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()

    async def _await_completion(self) -> None:
        """Poll OTA status until the device flashes and reboots (or fails)."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _INSTALL_TIMEOUT_SECONDS
        seen_verifying = False
        unreachable_polls = 0

        while loop.time() < deadline:
            await asyncio.sleep(_PROGRESS_POLL_SECONDS)
            try:
                status = await self.runtime.client.async_ota_status()
            except MaconControllerError:
                # The controller stops its HTTP server just before flashing and
                # then reboots, so it becomes unreachable at the tail of a
                # successful update. Treat sustained unreachability (or any
                # drop after verifying) as the apply/reboot phase = success.
                unreachable_polls += 1
                if seen_verifying or unreachable_polls >= _REBOOT_CONFIRM_POLLS:
                    return
                continue

            unreachable_polls = 0
            if status.failed:
                raise HomeAssistantError(
                    status.error or "Firmware update failed"
                )
            self._attr_update_percentage = status.progress
            self.async_write_ha_state()
            if status.state == "ready_to_reboot":
                return
            if status.state == "verifying" or status.progress >= 100:
                seen_verifying = True

        raise HomeAssistantError(
            "Timed out waiting for the firmware update to complete"
        )
