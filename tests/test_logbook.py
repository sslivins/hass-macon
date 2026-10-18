"""Test that Macon faults and controller events are explained in Home Assistant's activity log."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.macon.const import (
    DIAGNOSTICS_INTERVAL,
    DOMAIN,
    controller_event_entity,
)
from custom_components.macon.logbook import async_describe_events

from .conftest import make_diagnostics, make_snapshot
from .test_integration import entity_id, setup_entry

P06 = {
    "active": True,
    "code": "P06",
    "name": "LOW_PRESSURE",
    "description": "Refrigerant pressure too low",
    "severity": "critical",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Start the recorder before hass, which the activity log needs."""
    yield


async def test_fault_events_are_described(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    fault = entity_id(hass, SENSOR_DOMAIN, "arctic-001_fault_code")
    device_id = er.async_get(hass).async_get(fault).device_id
    dr.async_get(hass).async_update_device(
        device_id, name_by_user="Arctic Heatpump #1"
    )

    describers: dict = {}
    async_describe_events(
        hass,
        lambda domain, event_type, fn: describers.__setitem__(
            event_type, (domain, fn)
        ),
    )
    domain, describe = describers["macon_fault"]
    assert domain == DOMAIN

    onset = Event("macon_fault", {"device_id": "arctic-001", **P06})
    assert describe(onset) == {
        "entity_id": fault,
        "name": "Arctic Heatpump #1",
        "message": "reported fault P06: Refrigerant pressure too low",
    }

    cleared = Event(
        "macon_fault", {"device_id": "arctic-001", "active": False, "code": None}
    )
    assert describe(cleared)["message"] == "fault cleared"

    # A controller this Home Assistant no longer knows still reads sensibly.
    orphan = Event(
        "macon_fault",
        {"device_id": "gone", "active": True, "code": "E01", "description": None},
    )
    assert describe(orphan) == {
        "name": "Heat pump",
        "message": "reported fault E01",
    }


async def test_fault_appears_in_activity_log(
    hass: HomeAssistant,
    hass_ws_client,
    mock_clients: dict[str, MagicMock],
) -> None:
    # The activity log depends on the frontend, whose package isn't installed
    # for tests; it plays no part in recording or describing events.
    hass.config.components.add("frontend")
    assert await async_setup_component(hass, "logbook", {})
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    fault = entity_id(hass, SENSOR_DOMAIN, "arctic-001_fault_code")
    start = dt_util.utcnow()

    client.snapshot_callback(
        make_snapshot("arctic-001", revision=2, operation="fault", error=P06)
    )
    await hass.async_block_till_done()
    client.snapshot_callback(make_snapshot("arctic-001", revision=3))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    ws = await hass_ws_client()
    await ws.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": start.isoformat(),
            "entity_ids": [fault],
        }
    )
    response = await ws.receive_json()
    assert response["success"]
    messages = [entry.get("message") for entry in response["result"]]
    assert "reported fault P06: Refrigerant pressure too low" in messages
    assert "fault cleared" in messages


def _controller_describer(hass: HomeAssistant):
    describers: dict = {}
    async_describe_events(
        hass,
        lambda domain, event_type, fn: describers.__setitem__(event_type, (domain, fn)),
    )
    domain, describe = describers["macon_controller_event"]
    assert domain == DOMAIN
    return describe


@pytest.mark.parametrize(
    ("event_type", "details", "message"),
    [
        (
            "wifi_lost",
            {"reason": 201, "reason_key": "network_not_found"},
            "lost Wi-Fi for over a minute (network not found)",
        ),
        ("wifi_lost", {"reason_key": "other"}, "lost Wi-Fi for over a minute"),
        ("wifi_restored", {"down_s": 94}, "Wi-Fi restored after 1 min 34 s"),
        ("wifi_restored", {"down_s": 7260}, "Wi-Fi restored after 2 h 1 min"),
        (
            "wifi_unstable",
            {"drops": 4},
            "Wi-Fi unstable: 4 short drops in the last hour",
        ),
        (
            "network_unreachable",
            {},
            "lost its network connection while Wi-Fi stayed up",
        ),
        (
            "network_recovered",
            {"recovery": "wifi_bounce"},
            "network connection recovered by reconnecting Wi-Fi",
        ),
        (
            "network_recovered",
            {"recovery": "reboot"},
            "restarted to recover its network connection",
        ),
        ("web_server_down", {"cause": "no_memory"}, "web server stopped (out of memory)"),
        (
            "web_server_recovered",
            {"recovery": "reboot"},
            "restarted to recover its web server",
        ),
        ("application_crash", {}, "crashed and restarted"),
        (
            "watchdog_reset",
            {"watchdog": "startup"},
            "restarted during startup, likely after a power interruption",
        ),
        ("watchdog_reset", {"watchdog": "task"}, "was restarted by its watchdog"),
        (
            "brownout_reset",
            {},
            "restarted after its supply voltage dipped (brownout)",
        ),
        ("disconnected", {}, "lost communication with the heat pump"),
        ("something_new", {}, "something new"),
    ],
)
async def test_controller_events_are_described(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    event_type: str,
    details: dict,
    message: str,
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    describe = _controller_describer(hass)
    entry = describe(
        Event(
            "macon_controller_event",
            {
                "device_id": "arctic-001",
                "type": event_type,
                "details": details,
                "timestamp": None,
            },
        )
    )
    platform, key = controller_event_entity(event_type)
    assert entry["message"] == message
    assert entry["entity_id"] == entity_id(hass, platform, f"arctic-001_{key}")


async def test_late_controller_event_says_when_it_happened(
    hass: HomeAssistant, mock_clients: dict[str, MagicMock]
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")
    describe = _controller_describer(hass)
    happened = dt_util.utcnow() - timedelta(minutes=30)
    late = Event(
        "macon_controller_event",
        {
            "device_id": "arctic-001",
            "type": "wifi_lost",
            "details": {},
            "timestamp": happened.isoformat(),
        },
    )
    local = dt_util.as_local(happened)
    if local.date() == dt_util.as_local(late.time_fired).date():
        when = f"{local:%H:%M}"
    else:
        when = f"{local:%Y-%m-%d %H:%M}"
    assert describe(late)["message"] == f"lost Wi-Fi for over a minute (at {when})"

    prompt = Event(
        "macon_controller_event",
        {
            "device_id": "arctic-001",
            "type": "wifi_lost",
            "details": {},
            "timestamp": dt_util.utcnow().isoformat(),
        },
    )
    assert describe(prompt)["message"] == "lost Wi-Fi for over a minute"


async def test_controller_event_appears_in_activity_log(
    hass: HomeAssistant,
    hass_ws_client,
    mock_clients: dict[str, MagicMock],
) -> None:
    hass.config.components.add("frontend")
    assert await async_setup_component(hass, "logbook", {})
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    wifi = entity_id(hass, "binary_sensor", "arctic-001_push_connected")
    start = dt_util.utcnow()
    lost = {
        "type": "wifi_lost",
        "category": "problems",
        "boot_id": 7,
        "uptime_ms": 90_000,
        "timestamp": int(start.timestamp()),
        "payload": 2,
        "details": {"reason": 2, "reason_key": "signal_lost"},
    }

    client.async_fetch_diagnostics.return_value = make_diagnostics(events=[])
    async_fire_time_changed(hass, start + DIAGNOSTICS_INTERVAL)
    await hass.async_block_till_done()
    client.async_fetch_diagnostics.return_value = make_diagnostics(events=[lost])
    async_fire_time_changed(hass, start + DIAGNOSTICS_INTERVAL * 2)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    ws = await hass_ws_client()
    await ws.send_json(
        {
            "id": 1,
            "type": "logbook/get_events",
            "start_time": start.isoformat(),
            "entity_ids": [wifi],
        }
    )
    response = await ws.receive_json()
    assert response["success"]
    messages = [entry.get("message") for entry in response["result"]]
    assert any(
        message and message.startswith("lost Wi-Fi for over a minute (signal lost)")
        for message in messages
    ), response["result"]
