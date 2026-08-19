"""Constants for the Macon Heat Pump Controller integration."""

from homeassistant.const import Platform

DOMAIN = "macon"

CONF_DEVICE_ID = "device_id"
CONF_FINGERPRINT = "fingerprint"
CONF_TOKEN = "token"
DEFAULT_PORT = 8443

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
]

EVENT_MACON_FAULT = "macon_fault"

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
