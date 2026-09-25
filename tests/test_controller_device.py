"""Tests for the controller/heat-pump device split and controller health."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pymacon import (
    ClientStatus,
    MaconCommandConflictError,
    MaconConnectionError,
    MaconControlUnavailableError,
)
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
)

from custom_components.macon.const import DIAGNOSTICS_INTERVAL, DOMAIN

from .conftest import make_diagnostics, make_snapshot
from .test_integration import entity_id, make_entry, setup_entry

HEAT_PUMP = (DOMAIN, "arctic-001:heat_pump")
CONTROLLER = (DOMAIN, "arctic-001")


def _state(hass: HomeAssistant, platform: str, key: str) -> str:
    return hass.states.get(entity_id(hass, platform, f"arctic-001_{key}")).state


async def test_fresh_install_creates_controller_and_heat_pump(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    controller = devices.async_get_device(identifiers={CONTROLLER})
    heat_pump = devices.async_get_device(identifiers={HEAT_PUMP})
    assert controller is not None and heat_pump is not None
    assert controller.manufacturer == "Arctic"
    assert controller.sw_version == "1.2.3"
    assert controller.configuration_url == "http://controller.local/"
    assert heat_pump.manufacturer == "Macon"
    assert heat_pump.sw_version is None
    assert heat_pump.name == "Macon Heat Pump -001"
    assert heat_pump.via_device_id == controller.id

    def device_of(platform: str, key: str) -> str | None:
        entry = entities.async_get(entity_id(hass, platform, f"arctic-001_{key}"))
        return entry.device_id

    assert device_of(SENSOR_DOMAIN, "tank_temperature") == heat_pump.id
    assert device_of(SENSOR_DOMAIN, "ip_address") == controller.id
    assert device_of(SENSOR_DOMAIN, "brownout_count") == controller.id
    assert device_of(UPDATE_DOMAIN, "firmware_update") == controller.id
    assert device_of(BUTTON_DOMAIN, "restart") == controller.id


async def test_legacy_single_device_is_kept_as_the_heat_pump(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    """The pre-split registry row keeps its id, area, and heat-pump entities;
    controller entities move to a new controller device without renaming."""
    entry = make_entry("arctic-001", "controller.local")
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    area = ar.async_get(hass).async_create("Mechanical room")
    legacy = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={CONTROLLER},
        name=entry.title,
        manufacturer="Macon",
        model="Macon Heat Pump Controller",
        sw_version="1.2.0",
    )
    devices.async_update_device(legacy.id, area_id=area.id)
    tank = entities.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "arctic-001_tank_temperature",
        config_entry=entry,
        device_id=legacy.id,
        suggested_object_id="old_tank",
    )
    ip = entities.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "arctic-001_ip_address",
        config_entry=entry,
        device_id=legacy.id,
        suggested_object_id="old_ip",
    )
    firmware = entities.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "arctic-001_firmware_update",
        config_entry=entry,
        device_id=legacy.id,
        suggested_object_id="old_firmware",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    heat_pump = devices.async_get_device(identifiers={HEAT_PUMP})
    controller = devices.async_get_device(identifiers={CONTROLLER})
    assert heat_pump is not None and controller is not None
    assert heat_pump.id == legacy.id
    assert heat_pump.area_id == area.id
    assert heat_pump.sw_version is None
    assert heat_pump.via_device_id == controller.id
    assert controller.id != legacy.id
    assert controller.sw_version == "1.2.3"

    assert entities.async_get(tank.entity_id).device_id == heat_pump.id
    assert entities.async_get(ip.entity_id).device_id == controller.id
    assert entities.async_get(firmware.entity_id).device_id == controller.id
    # Entity ids are a user contract; the split must not rename them.
    assert tank.entity_id == "sensor.old_tank"
    assert hass.states.get("sensor.old_ip").state == "192.168.1.21"

    # A second setup is a no-op: no third device, no re-keying.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(devices, entry.entry_id)) == 2


async def test_controller_health_entities(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    before = dt_util.utcnow()
    await setup_entry(hass, "arctic-001", "controller.local")

    assert _state(hass, SENSOR_DOMAIN, "brownout_count") == "2"
    assert _state(hass, SENSOR_DOMAIN, "panic_count") == "1"
    assert _state(hass, SENSOR_DOMAIN, "watchdog_count") == "0"
    assert _state(hass, SENSOR_DOMAIN, "last_reset_reason") == "power_on"
    assert _state(hass, SENSOR_DOMAIN, "bus_role") == "master"
    assert _state(hass, SENSOR_DOMAIN, "bus_consecutive_failures") == "0"
    assert _state(hass, SENSOR_DOMAIN, "wifi_disconnect_count") == "3"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "safe_mode") == "off"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "bus_problem") == "off"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "time_sync_problem") == "off"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "push_connected") == "on"

    booted = datetime.fromisoformat(_state(hass, SENSOR_DOMAIN, "last_boot"))
    expected = before - timedelta(hours=1)
    assert abs((booted - expected).total_seconds()) < 5
    last_ok = datetime.fromisoformat(_state(hass, SENSOR_DOMAIN, "bus_last_ok"))
    assert last_ok - booted == timedelta(milliseconds=3_599_000)

    entities = er.async_get(hass)
    for key in ("wifi_rssi", "wifi_ssid", "internal_free_memory", "bus_polls_ok"):
        registry_entry = entities.async_get(
            entity_id(hass, SENSOR_DOMAIN, f"arctic-001_{key}")
        )
        assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    button = entities.async_get(
        entity_id(hass, BUTTON_DOMAIN, "arctic-001_restart")
    )
    assert button.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_boot_time_is_stable_within_a_boot(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    first = _state(hass, SENSOR_DOMAIN, "last_boot")

    # Uptime advances in step with wall time, but even with poll jitter the
    # boot timestamp is computed once per boot and must not move.
    client.async_fetch_diagnostics.return_value = make_diagnostics(
        uptime_ms=3_600_000 + 61_234
    )
    async_fire_time_changed(hass, dt_util.utcnow() + DIAGNOSTICS_INTERVAL)
    await hass.async_block_till_done()
    assert client.async_fetch_diagnostics.await_count == 2
    assert _state(hass, SENSOR_DOMAIN, "last_boot") == first


@pytest.mark.parametrize(
    ("overrides", "key", "expected"),
    [
        ({"last_reset_reason": "cosmic_ray"}, "last_reset_reason", "unknown"),
        (
            {"rs485": {"role": "future_mode", "last_ok_uptime_ms": None}},
            "bus_role",
            "unknown",
        ),
    ],
)
async def test_unknown_enum_values_map_to_unknown(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    overrides: dict,
    key: str,
    expected: str,
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    client.async_fetch_diagnostics.return_value = make_diagnostics(**overrides)
    async_fire_time_changed(hass, dt_util.utcnow() + DIAGNOSTICS_INTERVAL)
    await hass.async_block_till_done()
    assert _state(hass, SENSOR_DOMAIN, key) == expected


@pytest.mark.parametrize(
    ("overrides", "key", "expected"),
    [
        ({"safe_mode": True}, "safe_mode", "on"),
        (
            {"rs485": {"role": "blocked", "last_ok_uptime_ms": None}},
            "bus_problem",
            "on",
        ),
        (
            {"rs485": {"role": "master", "consecutive_failures": 12}},
            "bus_problem",
            "on",
        ),
        (
            {"rs485": {"role": "master", "consecutive_failures": 2}},
            "bus_problem",
            "off",
        ),
        (
            {"rs485": {"role": "listener", "frames_ok": 10}},
            "bus_problem",
            "off",
        ),
        ({"time_synced": False, "uptime_ms": 60_000}, "time_sync_problem", "off"),
        (
            {"time_synced": False, "uptime_ms": 3_600_000},
            "time_sync_problem",
            "on",
        ),
    ],
)
async def test_problem_sensors(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    overrides: dict,
    key: str,
    expected: str,
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    client.async_fetch_diagnostics.return_value = make_diagnostics(**overrides)
    async_fire_time_changed(hass, dt_util.utcnow() + DIAGNOSTICS_INTERVAL)
    await hass.async_block_till_done()
    assert _state(hass, BINARY_SENSOR_DOMAIN, key) == expected


async def test_diagnostics_failure_only_affects_controller_health(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    client.async_fetch_diagnostics.side_effect = MaconConnectionError("boom")
    async_fire_time_changed(hass, dt_util.utcnow() + DIAGNOSTICS_INTERVAL)
    await hass.async_block_till_done()

    assert _state(hass, SENSOR_DOMAIN, "brownout_count") == "unavailable"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "safe_mode") == "unavailable"
    assert _state(hass, SENSOR_DOMAIN, "tank_temperature") == "42.0"
    assert _state(hass, SENSOR_DOMAIN, "ip_address") == "192.168.1.21"

    client.async_fetch_diagnostics.side_effect = None
    async_fire_time_changed(
        hass, dt_util.utcnow() + DIAGNOSTICS_INTERVAL * 2
    )
    await hass.async_block_till_done()
    assert _state(hass, SENSOR_DOMAIN, "brownout_count") == "2"


async def test_old_firmware_without_diagnostics(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    def create(host, token, fingerprint, **kwargs):
        client = factory(host, token, fingerprint, **kwargs)
        client.capabilities = replace(
            client.capabilities, diagnostics=False, restart=False
        )
        return client

    from custom_components import macon

    factory = macon.MaconClient.side_effect
    macon.MaconClient.side_effect = create
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]

    client.async_fetch_diagnostics.assert_not_awaited()
    assert _state(hass, SENSOR_DOMAIN, "brownout_count") == "unavailable"
    assert _state(hass, SENSOR_DOMAIN, "tank_temperature") == "42.0"
    assert _state(hass, BINARY_SENSOR_DOMAIN, "push_connected") == "on"


async def test_new_boot_refreshes_diagnostics_immediately(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    assert client.async_fetch_diagnostics.await_count == 1

    client.async_fetch_diagnostics.return_value = make_diagnostics(
        boot_id="boot-2", uptime_ms=5_000, last_reset_reason="brownout"
    )
    rebooted = replace(make_snapshot("arctic-001", revision=1), boot_id="boot-2")
    client.snapshot_callback(rebooted)
    await hass.async_block_till_done()

    assert client.async_fetch_diagnostics.await_count == 2
    assert _state(hass, SENSOR_DOMAIN, "last_reset_reason") == "brownout"
    # Further snapshots from the same boot don't trigger more polls.
    client.snapshot_callback(replace(rebooted, revision=2))
    await hass.async_block_till_done()
    assert client.async_fetch_diagnostics.await_count == 2


async def test_push_connection_follows_stream_status(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    client.status_callback(ClientStatus(True, False, None))
    await hass.async_block_till_done()
    assert _state(hass, BINARY_SENSOR_DOMAIN, "push_connected") == "off"


async def _enable_restart_button(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> tuple[str, MagicMock]:
    entry = await setup_entry(hass, "arctic-001", "controller.local")
    entities = er.async_get(hass)
    button = entity_id(hass, BUTTON_DOMAIN, "arctic-001_restart")
    entities.async_update_entity(button, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    return button, mock_clients["controller.local"]


async def test_restart_button_names_current_boot(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    button, client = await _enable_restart_button(hass, mock_clients)
    assert hass.states.get(button).state != "unavailable"

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {"entity_id": button}, blocking=True
    )
    client.async_restart.assert_awaited_once_with(boot_id="boot-1")


@pytest.mark.parametrize(
    "error",
    [
        MaconControlUnavailableError("ota"),
        MaconCommandConflictError("stale"),
        MaconConnectionError("down"),
    ],
)
async def test_restart_button_errors_surface(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    error: Exception,
) -> None:
    button, client = await _enable_restart_button(hass, mock_clients)
    client.async_restart.side_effect = error
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN, "press", {"entity_id": button}, blocking=True
        )
