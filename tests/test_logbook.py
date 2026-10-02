"""Test that Macon faults are explained in Home Assistant's activity log."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.macon.const import DOMAIN
from custom_components.macon.logbook import async_describe_events

from .conftest import make_snapshot
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
