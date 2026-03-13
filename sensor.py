"""Sensor platform for SwitchBot API."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .api import SwitchBotApiError, async_request, generate_auth_payload
from .const import (
    AUTH_CHECK_INTERVAL_SECONDS,
    AUTH_HEADER_TTL_SECONDS,
    CONF_SECRET,
    CONF_TOKEN,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

HEADER_REFRESH_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)
AUTH_CHECK_INTERVAL = timedelta(seconds=AUTH_CHECK_INTERVAL_SECONDS)

ENTITY_DESCRIPTION = SensorEntityDescription(
    key="headers",
    icon="mdi:key-chain",
)

STATE_CONNECTED = "connected"
STATE_AUTH_FAILED = "authentication_failed"
STATE_CONNECTION_ERROR = "connection_error"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry."""
    async_add_entities([SwitchBotAuthSensor(hass, config_entry)])


class SwitchBotAuthSensor(SensorEntity):
    """SwitchBot API authentication status and header generator.

    State reflects whether the API credentials are valid:
    - connected: credentials validated successfully
    - authentication_failed: token or secret is invalid
    - connection_error: cannot reach the SwitchBot API

    Attributes contain fresh auth headers regenerated every 55 seconds.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description = ENTITY_DESCRIPTION

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the sensor."""
        self._hass = hass
        self._config_entry = config_entry
        self._token = config_entry.data[CONF_TOKEN]
        self._secret = config_entry.data[CONF_SECRET]
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        self._attr_name = "API status"
        self._attr_unique_id = f"{config_entry.entry_id}_switchbot_auth"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="SwitchBot",
            model="Cloud API",
            name="SwitchBot API",
        )

    async def async_added_to_hass(self) -> None:
        """Start header refresh and auth check timers."""
        self._refresh_headers()
        await self._check_auth()

        self.async_on_remove(
            async_track_time_interval(
                self._hass,
                self._header_refresh_callback,
                HEADER_REFRESH_INTERVAL,
            )
        )
        self.async_on_remove(
            async_track_time_interval(
                self._hass,
                self._auth_check_callback,
                AUTH_CHECK_INTERVAL,
            )
        )

    async def _header_refresh_callback(self, _) -> None:
        """Regenerate auth headers on the 55-second interval."""
        self._refresh_headers()
        self.async_write_ha_state()

    async def _auth_check_callback(self, _) -> None:
        """Validate credentials against the API on the 10-minute interval."""
        await self._check_auth()

    async def async_update(self) -> None:
        """Handle manual entity update -- refresh headers and validate."""
        self._refresh_headers()
        await self._check_auth()

    def _refresh_headers(self) -> None:
        """Generate fresh auth headers and store in attributes."""
        auth = generate_auth_payload(
            self._token,
            self._secret,
            ttl_seconds=AUTH_HEADER_TTL_SECONDS,
        )
        self._attr_extra_state_attributes = auth

    async def _check_auth(self) -> None:
        """Validate credentials by calling the SwitchBot API."""
        try:
            await async_request(
                self._hass, "GET", "/devices", self._token, self._secret
            )
            self._attr_native_value = STATE_CONNECTED
        except SwitchBotApiError as exc:
            if exc.auth_failed:
                self._attr_native_value = STATE_AUTH_FAILED
                _LOGGER.warning("SwitchBot API authentication failed -- check your token and secret")
            else:
                self._attr_native_value = STATE_CONNECTION_ERROR
                _LOGGER.warning("SwitchBot API connection error: %s", exc)

        self.async_write_ha_state()
