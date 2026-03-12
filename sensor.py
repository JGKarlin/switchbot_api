"""Sensor platform for SwitchBot API."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .api import generate_auth_headers
from .const import CONF_SECRET, CONF_TOKEN, DOMAIN, SCAN_INTERVAL_SECONDS

SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)
ENTITY_DESCRIPTION = SensorEntityDescription(
    key="headers",
    icon="mdi:key-chain",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry."""
    async_add_entities([SwitchBotAuthSensor(hass, config_entry)])


class SwitchBotAuthSensor(SensorEntity):
    """Representation of a SwitchBot API Sensor."""

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
        self._attr_name = "Auth headers"
        self._attr_unique_id = f"{config_entry.entry_id}_switchbot_api"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="SwitchBot",
            model="Cloud API",
            name="SwitchBot API",
        )

    async def async_added_to_hass(self) -> None:
        """Handle added to Hass."""
        await self.async_update_auth()
        self.async_on_remove(
            async_track_time_interval(
                self._hass,
                self.async_update_callback,
                SCAN_INTERVAL,
            )
        )

    async def async_update_callback(self, _):
        """Handle the interval update callback."""
        await self.async_update_auth()

    async def async_update_auth(self):
        """Update authentication parameters asynchronously."""
        headers = generate_auth_headers(self._token, self._secret)

        self._attr_native_value = "ready"
        self._attr_extra_state_attributes = {
            "authorization": headers["Authorization"],
            "t": headers["t"],
            "nonce": headers["nonce"],
            "sign": headers["sign"],
        }
        self.async_write_ha_state()
