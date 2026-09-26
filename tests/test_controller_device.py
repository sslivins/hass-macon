"""Tests for the single Macon device and controller health."""

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
from homeassistant.const import EntityCategory
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

from custom_components.macon.binary_sensor import (
    CONTROLLER_DESCRIPTIONS as CONTROLLER_BINARY_SENSORS,
)
from custom_components.macon.const import DIAGNOSTICS_INTERVAL, DOMAIN
from custom_components.macon.sensor import CONTROLLER_SENSORS, INFO_SENSORS

from .conftest import make_diagnostics, make_snapshot
from .test_integration import entity_id, make_entry, setup_entry

SPLIT_HEAT_PUMP = (DOMAIN, "arctic-001:heat_pump")
DEVICE = (DOMAIN, "arctic-001")

# Everything about the controller itself; all other entities describe the
# heat pump and must stay out of the diagnostic/config sections.
CONTROLLER_KEYS = {
    *(d.key for d in CONTROLLER_SENSORS),
    *(d.key for d in CONTROLLER_BINARY_SENSORS),
    *(d.key for d in INFO_SENSORS),
    "push_connected",
    "firmware_update",
    "restart",
}


def _state(hass: HomeAssistant, platform: str, key: str) -> str:
    return hass.states.get(entity_id(hass, platform, f"arctic-001_{key}")).state


async def test_one_device_holds_heat_pump_and_controller(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    entry = await setup_entry(hass, "arctic-001", "controller.local")
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    device_entries = dr.async_entries_for_config_entry(devices, entry.entry_id)
    assert len(device_entries) == 1
    device = device_entries[0]
    assert device.identifiers == {DEVICE}
    assert device.manufacturer == "Macon"
    assert device.sw_version == "1.2.3"
    assert device.configuration_url == "https://controller.local"
    assert device.via_device_id is None

    registered = er.async_entries_for_config_entry(entities, entry.entry_id)
    assert registered
    assert {e.device_id for e in registered} == {device.id}


async def test_controller_entities_have_their_own_section(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    """Controller health is diagnostic (restart/firmware are config); every
    heat-pump entity stays in the device's controls and sensors."""
    entry = await setup_entry(hass, "arctic-001", "controller.local")
    registered = er.async_entries_for_config_entry(
        er.async_get(hass), entry.entry_id
    )
    by_key = {e.unique_id.removeprefix("arctic-001_"): e for e in registered}
    assert CONTROLLER_KEYS <= set(by_key)
    for key, registry_entry in by_key.items():
        if key in {"firmware_update", "restart"}:
            expected = EntityCategory.CONFIG
        elif key in CONTROLLER_KEYS:
            expected = EntityCategory.DIAGNOSTIC
        else:
            expected = None
        assert registry_entry.entity_category == expected, key


@pytest.mark.skipif(
    not hasattr(dr.DeviceRegistry, "async_get_device_by_identifier"),
    reason="this Home Assistant has no per-entry device lookup",
)
async def test_setup_avoids_deprecated_async_get_device(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deprecated(*args: object, **kwargs: object) -> None:
        raise AssertionError("async_get_device is deprecated")

    monkeypatch.setattr(dr.DeviceRegistry, "async_get_device", deprecated)
    entry = await setup_entry(hass, "arctic-001", "controller.local")
    assert dr.async_get(hass).async_get_device_by_identifier(
        DEVICE, entry.entry_id
    )


async def test_split_devices_are_merged_back_into_one(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    """0.8.0-0.8.3 registered a controller device and a heat-pump device. The
    heat-pump row (the user's original device) is kept with its id, name, and
    area; controller entities move onto it without being renamed."""
    entry = make_entry("arctic-001", "controller.local")
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    area = ar.async_get(hass).async_create("Mechanical room")
    controller = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={DEVICE},
        name=entry.title,
        manufacturer="Arctic",
        model="Arctic Heat Pump Controller",
    )
    heat_pump = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={SPLIT_HEAT_PUMP},
        name="Macon Heat Pump -001",
        manufacturer="Macon",
        model="Heat pump",
    )
    devices.async_update_device(
        heat_pump.id,
        area_id=area.id,
        name_by_user="Heat Pump 1",
        via_device_id=controller.id,
    )

    def register(
        platform: str, key: str, device_id: str, object_id: str
    ) -> str:
        return entities.async_get_or_create(
            platform,
            DOMAIN,
            f"arctic-001_{key}",
            config_entry=entry,
            device_id=device_id,
            suggested_object_id=object_id,
        ).entity_id

    tank = register(SENSOR_DOMAIN, "tank_temperature", heat_pump.id, "old_tank")
    brownouts = register(
        SENSOR_DOMAIN, "brownout_count", controller.id, "old_brownouts"
    )
    firmware = register(
        UPDATE_DOMAIN, "firmware_update", controller.id, "old_firmware"
    )
    polls = register(SENSOR_DOMAIN, "bus_polls_ok", controller.id, "old_polls")
    entities.async_update_entity(
        polls, disabled_by=er.RegistryEntryDisabler.INTEGRATION
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(devices, entry.entry_id)
    assert [d.id for d in device_entries] == [heat_pump.id]
    merged = device_entries[0]
    assert merged.identifiers == {DEVICE}
    assert merged.area_id == area.id
    assert merged.name_by_user == "Heat Pump 1"
    assert merged.via_device_id is None
    assert merged.manufacturer == "Macon"
    assert merged.sw_version == "1.2.3"

    for entity in (tank, brownouts, firmware, polls):
        registry_entry = entities.async_get(entity)
        assert registry_entry is not None, entity
        assert registry_entry.device_id == heat_pump.id
    # Entity ids are a user contract; the merge must not rename them.
    assert tank == "sensor.old_tank"
    assert hass.states.get("sensor.old_brownouts").state == "2"

    # A second setup is a no-op.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert [
        d.id for d in dr.async_entries_for_config_entry(devices, entry.entry_id)
    ] == [heat_pump.id]


async def test_pre_split_device_is_kept(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    """Upgrading straight from a pre-0.8 release leaves the single device and
    its entities as they were."""
    entry = make_entry("arctic-001", "controller.local")
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    legacy = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={DEVICE},
        name=entry.title,
        manufacturer="Macon",
        sw_version="1.2.0",
    )
    tank = entities.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "arctic-001_tank_temperature",
        config_entry=entry,
        device_id=legacy.id,
        suggested_object_id="old_tank",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(devices, entry.entry_id)
    assert [d.id for d in device_entries] == [legacy.id]
    assert device_entries[0].sw_version == "1.2.3"
    assert entities.async_get(tank.entity_id).device_id == legacy.id


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
    assert abs((last_ok - (before - timedelta(seconds=1))).total_seconds()) < 5

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


async def test_last_rs485_response_is_anchored_to_each_poll(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    """Drift between the controller timer and HA's clock must not leak into
    the last-response time: after a long uptime the controller's uptime runs
    ahead of wall time, but a response 2 s before the poll still reads 2 s
    before the poll, never in the future."""
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    drifted_uptime = 3_600_000 + 120_000  # 2 min ahead of HA's clock
    client.async_fetch_diagnostics.return_value = make_diagnostics(
        uptime_ms=drifted_uptime,
        rs485={
            "role": "master",
            "last_ok_uptime_ms": drifted_uptime - 2_000,
            "consecutive_failures": 0,
        },
    )
    polled = dt_util.utcnow() + DIAGNOSTICS_INTERVAL
    async_fire_time_changed(hass, polled)
    await hass.async_block_till_done()
    last_ok = datetime.fromisoformat(_state(hass, SENSOR_DOMAIN, "bus_last_ok"))
    assert last_ok <= dt_util.utcnow()
    assert abs((dt_util.utcnow() - last_ok).total_seconds() - 2) < 2


async def test_ipv6_host_builds_valid_configuration_url(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "fe80::1")
    controller = dr.async_get(hass).async_get_device(identifiers={DEVICE})
    assert controller.configuration_url == "https://[fe80::1]"


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
