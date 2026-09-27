"""Constants for the Macon Heat Pump Controller integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "macon"

CONF_DEVICE_ID = "device_id"
CONF_FINGERPRINT = "fingerprint"
CONF_TOKEN = "token"
DEFAULT_PORT = 8443

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
]

EVENT_MACON_FAULT = "macon_fault"

# 0.8.0-0.8.3 split each entry into a controller device and a heat-pump device
# keyed by ``<device_id>:heat_pump``; setup merges them back into one.
SPLIT_HEAT_PUMP_IDENTIFIER_SUFFIX = ":heat_pump"

# Controller health is polled, not pushed: it changes continuously and is kept
# out of the revisioned heat-pump snapshot on purpose.
DIAGNOSTICS_INTERVAL = timedelta(seconds=60)

# Reset reasons reported by the firmware (boot_stats_reset_reason_name(),
# lowercased). Anything else maps to "unknown".
RESET_REASONS: tuple[str, ...] = (
    "power_on",
    "external",
    "software",
    "panic",
    "interrupt_wdt",
    "task_wdt",
    "other_wdt",
    "deep_sleep",
    "brownout",
    "sdio",
    "usb",
    "jtag",
    "efuse_error",
    "power_glitch",
    "cpu_lockup",
)

# What the controller is doing on the RS485 bus.
BUS_ROLES: tuple[str, ...] = (
    "master",
    "listener",
    "blocked",
    "demo",
    "inactive",
)

STATE_UNKNOWN_ENUM = "unknown"

# Working modes as the unit numbers them (0-6). Only cooling, heating,
# hot_water and hot_water_cooling can be selected; mode_2..mode_4 are heating
# variants the unit can be in but the controller never selects.
WORKING_MODES: tuple[str, ...] = (
    "cooling",
    "heating",
    "mode_2",
    "mode_3",
    "mode_4",
    "hot_water",
    "hot_water_cooling",
)

# Controllers before the bench mapping used these names for the same modes.
LEGACY_MODE_KEYS = {
    "floor_heating": "heating",
    "fan_coil_heating": "mode_2",
    "auto": "hot_water_cooling",
}

HEATING_MODES = frozenset({"heating", "mode_2", "mode_3", "mode_4"})


def normalize_mode(mode: str) -> str:
    """Map a controller mode key (old or new) to the current name."""
    return LEGACY_MODE_KEYS.get(mode, mode)


def setpoint_kind(mode: str, operation: str) -> str | None:
    """Which setpoint the unit works to in ``mode``.

    Modes 1 and 2 use the heating setpoint. Modes 3 and 4 use installer
    parameters that aren't exposed, so they have none here. Hot water /
    cooling works to the cooling setpoint while cooling, otherwise hot water.
    """
    mode = normalize_mode(mode)
    if mode == "cooling":
        return "cooling"
    if mode == "hot_water":
        return "hot_water"
    if mode in ("heating", "mode_2"):
        return "heating"
    if mode == "hot_water_cooling":
        return "cooling" if operation == "cooling" else "hot_water"
    return None

# Consecutive failed polls before the RS485 link is reported as a problem.
# The master polls roughly once a second, so this rides out single dropouts.
BUS_PROBLEM_CONSECUTIVE_FAILURES = 5

# Don't report "time not synced" until SNTP has had a fair chance after boot.
TIME_SYNC_GRACE_MS = 10 * 60 * 1000

# Bundled Lovelace card. The version is appended to the resource URL as a cache
# buster, so it must be bumped in lockstep with CARD_VERSION inside
# www/macon-heat-pump-card.js whenever the card changes.
CARD_FILENAME = "macon-heat-pump-card.js"
CARD_URL_BASE = f"/{DOMAIN}_frontend"
CARD_VERSION = "0.2.8"

FAULT_STATE_OK = "ok"
FAULT_STATE_UNKNOWN = "unknown"

# Stable Arctic Controller fault codes, mirrored from the firmware error
# tables (heatpump_errors.cpp). Register 1 followed by register 2.
FAULT_CODES: tuple[str, ...] = (
    "E27",
    "E28",
    "E19",
    "E18",
    "E13",
    "E05",
    "E01",
    "E09",
    "E22",
    "E10",
    "E21",
    "r02",
    "E12",
    "r01",
    "PA",
    "r10",
    "P19",
    "r06",
    "FA",
    "r11",
    "r05",
    "P11",
    "P02",
    "P06",
    "P01",
    "P27",
    "E26",
    "EC",
    "ED",
    "P15",
    "P16",
    "r20",
)
