"""The SwitchBot API integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .services import (
    async_refresh_device_cache,
    async_reregister_send_command,
    async_setup_services,
    async_unload_services,
)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]

DEPRECATED_ENTITY_SUFFIXES = [
    "_device_list",
]


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up the SwitchBot API integration."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBot API from a config entry."""
    _cleanup_deprecated_entities(hass, entry)
    await async_refresh_device_cache(hass)
    await async_setup_services(hass)
    await async_reregister_send_command(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _cleanup_deprecated_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove entities that were created by older versions of this integration."""
    registry = er.async_get(hass)
    for suffix in DEPRECATED_ENTITY_SUFFIXES:
        unique_id = f"{entry.entry_id}{suffix}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is not None:
            registry.async_remove(entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await async_unload_services(hass)
    return unloaded
