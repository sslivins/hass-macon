"""Macon Heat Pump Controller integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pymacon import (
    MaconAuthenticationError,
    MaconCertificateError,
    MaconClient,
    MaconConnectionError,
    MaconProtocolError,
)

from .const import (
    CARD_FILENAME,
    CARD_URL_BASE,
    CARD_VERSION,
    CONF_DEVICE_ID,
    CONF_FINGERPRINT,
    CONF_TOKEN,
    DOMAIN,
    PLATFORMS,
)
from .runtime import MaconRuntime

_LOGGER = logging.getLogger(__name__)

FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and register it with the frontend.

    Runs once per Home Assistant instance no matter how many controllers are
    configured; registering the same static path twice raises.
    """
    if hass.data.get(FRONTEND_REGISTERED):
        return
    if "frontend" not in hass.config.components:
        # Headless setups (and the test harness) never load the frontend, so
        # there is nothing to serve the card to.
        return
    # Claim the slot before the first await so two config entries setting up
    # concurrently cannot both get past the guard.
    hass.data[FRONTEND_REGISTERED] = True

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL_BASE,
                str(Path(__file__).parent / "www"),
                cache_headers=False,
            )
        ]
    )
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILENAME}?v={CARD_VERSION}")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up one independently paired Macon heat pump controller."""
    try:
        await _async_register_card(hass)
    except Exception:  # noqa: BLE001 - a dashboard card must never block setup
        _LOGGER.warning(
            "Could not register the Macon heat pump card; the integration will "
            "still work but the custom card will be unavailable",
            exc_info=True,
        )

    client = MaconClient(
        entry.data[CONF_HOST],
        entry.data[CONF_TOKEN],
        entry.data[CONF_FINGERPRINT],
        device_id=entry.data[CONF_DEVICE_ID],
        port=entry.data[CONF_PORT],
        session=async_get_clientsession(hass),
    )
    runtime = MaconRuntime(hass, entry, client)
    try:
        await runtime.async_setup()
    except (
        MaconAuthenticationError,
        MaconCertificateError,
    ) as error:
        await runtime.async_shutdown()
        raise ConfigEntryAuthFailed from error
    except (MaconConnectionError, MaconProtocolError) as error:
        await runtime.async_shutdown()
        raise ConfigEntryNotReady from error

    entry.runtime_data = runtime
    setup_complete = False
    try:
        runtime.async_register_devices()
        await hass.config_entries.async_forward_entry_setups(
            entry, PLATFORMS
        )
        runtime.async_start_diagnostics()
        setup_complete = True
    finally:
        if not setup_complete:
            await runtime.async_shutdown()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload one controller without affecting other config entries."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
