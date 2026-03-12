"""Services for the SwitchBot API integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from .api import SwitchBotApiError, async_request
from .const import CONF_SECRET, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_DEVICES = "get_devices"
SERVICE_SEND_COMMAND = "send_command"

ATTR_DEVICE_ID = "device_id"
ATTR_COMMAND = "command"
ATTR_PARAMETER = "parameter"
ATTR_COMMAND_TYPE = "command_type"

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Optional(ATTR_COMMAND, default="turnOn"): str,
        vol.Optional(ATTR_PARAMETER, default="default"): vol.Any(str, dict),
        vol.Optional(ATTR_COMMAND_TYPE, default="command"): str,
    }
)


async def fetch_devices(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Fetch device list from SwitchBot API. Shared by service and options flow."""
    token = entry.data[CONF_TOKEN]
    secret = entry.data[CONF_SECRET]
    body = await async_request(hass, "GET", "/devices", token, secret)

    devices = []
    device_list = body.get("deviceList", [])
    infrared_remote_list = body.get("infraredRemoteList", [])

    for device in device_list:
        devices.append(
            {
                "device_id": device.get("deviceId"),
                "device_name": device.get("deviceName") or "Unnamed device",
                "device_type": device.get("deviceType") or "Unknown",
            }
        )

    for device in infrared_remote_list:
        devices.append(
            {
                "device_id": device.get("deviceId"),
                "device_name": device.get("deviceName") or "Unnamed remote",
                "device_type": device.get("remoteType", "Infrared remote"),
            }
        )

    devices.sort(key=lambda item: (item["device_name"].lower(), item["device_id"] or ""))

    return {
        "devices": devices,
        "device_count": len(devices),
        "physical_device_count": len(device_list),
        "infrared_remote_count": len(infrared_remote_list),
    }


async def async_get_devices(call: ServiceCall) -> ServiceResponse:
    """Fetch device list from SwitchBot API and return device names and IDs."""
    hass = call.hass
    entry = _get_config_entry(hass)
    if not entry:
        raise ServiceValidationError("No SwitchBot API configuration found")

    try:
        result = await fetch_devices(hass, entry)
    except SwitchBotApiError as exc:
        raise ServiceValidationError(str(exc)) from exc

    _LOGGER.debug("Fetched %s SwitchBot devices", result["device_count"])
    return result


async def async_send_command(call: ServiceCall) -> ServiceResponse | None:
    """Send a command to a SwitchBot device."""
    hass = call.hass
    entry = _get_config_entry(hass)
    if not entry:
        raise ServiceValidationError("No SwitchBot API configuration found")

    device_id = call.data.get(ATTR_DEVICE_ID)
    command = call.data.get(ATTR_COMMAND, "turnOn")
    parameter = call.data.get(ATTR_PARAMETER, "default")
    command_type = call.data.get(ATTR_COMMAND_TYPE, "command")

    if not device_id:
        raise ServiceValidationError("device_id is required")

    payload = {
        "command": command,
        "parameter": parameter,
        "commandType": command_type,
    }

    token = entry.data[CONF_TOKEN]
    secret = entry.data[CONF_SECRET]

    try:
        body = await async_request(
            hass,
            "POST",
            f"/devices/{device_id}/commands",
            token,
            secret,
            payload=payload,
        )
    except SwitchBotApiError as exc:
        raise ServiceValidationError(str(exc)) from exc

    if call.return_response:
        return {
            "device_id": device_id,
            "command": command,
            "parameter": parameter,
            "command_type": command_type,
            "body": body,
        }

    _LOGGER.debug("SwitchBot command sent to %s", device_id)
    return None


def _get_config_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Get the first SwitchBot API config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register SwitchBot API services."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_DEVICES):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DEVICES,
        async_get_devices,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_send_command,
        schema=SEND_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
