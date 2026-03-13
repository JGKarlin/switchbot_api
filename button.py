"""Button platform for SwitchBot API -- refresh device list."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .services import (
    DATA_CACHE_DEVICE_COUNT,
    DATA_CACHE_UPDATED_UTC,
    DATA_DEVICES,
    async_refresh_device_cache,
    async_reregister_send_command,
)

ENTITY_DESCRIPTION = ButtonEntityDescription(
    key="refresh_devices",
    icon="mdi:refresh",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the refresh button from a config entry."""
    async_add_entities([SwitchBotRefreshDevicesButton(hass, config_entry)])


class SwitchBotRefreshDevicesButton(ButtonEntity):
    """Button that refreshes the cached SwitchBot device list.

    The full device list is exposed via extra state attributes so it can
    be inspected directly from the entity detail view.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    entity_description = ENTITY_DESCRIPTION

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the button."""
        self._hass = hass
        self._config_entry = config_entry
        self._attr_name = "Refresh device list"
        self._attr_unique_id = f"{config_entry.entry_id}_refresh_devices"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="SwitchBot",
            model="Cloud API",
            name="SwitchBot API",
        )
        self._update_attributes()

    async def async_press(self) -> None:
        """Handle button press -- refresh device cache."""
        await async_refresh_device_cache(self._hass)
        await async_reregister_send_command(self._hass)
        self._update_attributes()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Update attributes when entity is added."""
        self._update_attributes()

    @callback
    def _update_attributes(self) -> None:
        """Build the full device list as extra state attributes."""
        domain_data = self._hass.data.get(DOMAIN, {})
        devices = domain_data.get(DATA_DEVICES, [])
        count = domain_data.get(DATA_CACHE_DEVICE_COUNT, 0)
        updated = domain_data.get(DATA_CACHE_UPDATED_UTC, "never")

        physical = []
        infrared = []
        for dev in devices:
            entry = f"{dev['device_name']} [{dev['device_type']}] — {dev['device_id']}"
            if dev.get("is_infrared"):
                infrared.append(entry)
            else:
                physical.append(entry)

        self._attr_extra_state_attributes = {
            "device_count": count,
            "physical_devices": len(physical),
            "infrared_remotes": len(infrared),
            "last_refreshed": updated,
            "physical_device_list": physical,
            "infrared_remote_list": infrared,
        }
