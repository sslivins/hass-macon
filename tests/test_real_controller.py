"""Home Assistant entities fed with real controller responses.

The other tests build controller data by hand. These use JSON captured from a
production controller (see fixtures/controller/README.md) and the real pymacon
parsers, so firmware or pymacon drift that breaks an entity fails here.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.logbook.helpers import is_sensor_continuous
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pymacon import ControllerDiagnostics, StateSnapshot
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.macon.const import DIAGNOSTICS_INTERVAL, DOMAIN

from .test_integration import setup_entry

FIXTURES = Path(__file__).parent / "fixtures" / "controller"

# Entities that are legitimately empty for this capture, and why. Anything
# else without a value means the integration no longer understands the data.
EXPECTED_EMPTY = {
    # Only reported while the controller is listening; this one drives the bus.
    "sensor.bus_frames_ok": "listener-only counter",
    "sensor.bus_resyncs": "listener-only counter",
    # The heat pump is idle, so there is no efficiency to report.
    "sensor.cop": "idle",
    # No Wi-Fi drop since boot.
    "sensor.wifi_last_disconnect_reason": "no disconnect yet",
}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def wire_payloads() -> dict[str, dict]:
    return {name: _load(name) for name in ("capabilities", "state", "diagnostics")}


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable the entities that are disabled by default, as HA core's tests do."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
        new_callable=PropertyMock,
    ):
        yield


def _entities(hass: HomeAssistant) -> list[er.RegistryEntry]:
    return sorted(
        (
            entry
            for entry in er.async_get(hass).entities.values()
            if entry.platform == DOMAIN
        ),
        key=lambda entry: entry.unique_id,
    )


def _key(entry: er.RegistryEntry) -> str:
    return f"{entry.domain}.{entry.unique_id.removeprefix('arctic-001_')}"


def _in_logbook(hass: HomeAssistant, entry: er.RegistryEntry) -> bool:
    """Whether a state change of this entity gets a logbook entry."""
    if entry.domain != SENSOR_DOMAIN:
        return True
    return not is_sensor_continuous(hass, er.async_get(hass), entry.entity_id)


async def test_every_entity_has_a_value(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    entity_registry_enabled_by_default: None,
) -> None:
    await setup_entry(hass, "arctic-001", "controller.local")

    empty = {
        _key(entry): hass.states.get(entry.entity_id).state
        for entry in _entities(hass)
        # A button's state is when it was last pressed.
        if entry.domain != BUTTON_DOMAIN
        and hass.states.get(entry.entity_id).state
        in (STATE_UNKNOWN, STATE_UNAVAILABLE)
    }
    assert empty == dict.fromkeys(EXPECTED_EMPTY, STATE_UNKNOWN)


async def test_routine_updates_do_not_reach_the_logbook(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    wire_payloads: dict[str, dict],
    entity_registry_enabled_by_default: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A minute of a steady heat pump must not add logbook entries.

    The logbook records every state change of an entity that isn't a
    measurement, so values that tick on every poll belong in attributes or
    measurement sensors.
    """
    await setup_entry(hass, "arctic-001", "controller.local")
    client = mock_clients["controller.local"]
    watched = [entry for entry in _entities(hass) if _in_logbook(hass, entry)]
    before = {entry.entity_id: hass.states.get(entry.entity_id).state for entry in watched}

    # One minute later: the heat pump is unchanged, the controller has kept
    # polling it, and a fresh push arrives with the same readings.
    diagnostics = copy.deepcopy(wire_payloads["diagnostics"])
    health = diagnostics["diagnostics"]
    health["uptime_ms"] += 60_000
    health["rs485"]["last_ok_uptime_ms"] += 60_000
    health["rs485"]["polls_ok"] += 60
    client.async_fetch_diagnostics.return_value = ControllerDiagnostics.from_dict(
        diagnostics
    )
    state = copy.deepcopy(wire_payloads["state"])
    state["revision"] += 1
    state["captured_at_ms"] += 60_000
    freezer.tick(DIAGNOSTICS_INTERVAL)
    client.snapshot_callback(StateSnapshot.from_dict(state))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_fetch_diagnostics.await_count == 2

    changed = {
        entity_id: (value, hass.states.get(entity_id).state)
        for entity_id, value in before.items()
        if hass.states.get(entity_id).state != value
    }
    assert changed == {}


async def test_entity_inventory(
    hass: HomeAssistant,
    mock_clients: dict[str, MagicMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Every entity and how it is presented.

    Adding, removing or recategorizing an entity changes this snapshot, so the
    change is visible in review. Update with ``pytest --snapshot-update``.
    """
    await setup_entry(hass, "arctic-001", "controller.local")
    inventory = {
        _key(entry): {
            "name": entry.original_name,
            "category": entry.entity_category,
            "device_class": entry.original_device_class,
            "unit": entry.unit_of_measurement,
            "state_class": (entry.capabilities or {}).get("state_class"),
            "enabled_by_default": entry.disabled_by is None,
            "in_logbook": _in_logbook(hass, entry),
        }
        for entry in _entities(hass)
    }
    assert inventory == snapshot
