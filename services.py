"""Services for the SwitchBot API integration."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError

from .api import SwitchBotApiError, async_request, generate_auth_payload
from .const import (
    AUTH_HEADER_TTL_SECONDS,
    CONF_SECRET,
    CONF_TOKEN,
    DOMAIN,
)
from .device_commands import (
    CommandDef,
    get_commands_for_device_type,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_DEVICES = "get_devices"
SERVICE_GET_AUTH_HEADERS = "get_auth_headers"
SERVICE_SEND_COMMAND = "send_command"

ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_ID = "device_id"
ATTR_COMMAND = "command"
ATTR_PARAMETER = "parameter"
ATTR_COMMAND_TYPE = "command_type"

DATA_DEVICES = "devices"
DATA_DEVICE_MAP = "device_map"
DATA_CACHE_UPDATED_UTC = "cache_updated_utc"
DATA_CACHE_DEVICE_COUNT = "cache_device_count"


async def fetch_devices(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Fetch device list from SwitchBot API. Shared by service and options flow."""
    token = entry.data[CONF_TOKEN]
    secret = entry.data[CONF_SECRET]
    body = await async_request(hass, "GET", "/devices", token, secret)

    devices: list[dict[str, Any]] = []
    device_list = body.get("deviceList", [])
    infrared_remote_list = body.get("infraredRemoteList", [])

    for device in device_list:
        devices.append(
            {
                "device_id": device.get("deviceId"),
                "device_name": device.get("deviceName") or "Unnamed device",
                "device_type": device.get("deviceType") or "Unknown",
                "is_infrared": False,
            }
        )

    for device in infrared_remote_list:
        devices.append(
            {
                "device_id": device.get("deviceId"),
                "device_name": device.get("deviceName") or "Unnamed remote",
                "device_type": device.get("remoteType", "Infrared remote"),
                "is_infrared": True,
            }
        )

    devices.sort(key=lambda item: (item["device_name"].lower(), item["device_id"] or ""))

    return {
        "devices": devices,
        "device_count": len(devices),
        "physical_device_count": len(device_list),
        "infrared_remote_count": len(infrared_remote_list),
    }


async def async_refresh_device_cache(hass: HomeAssistant) -> None:
    """Fetch and cache the device list for service dropdowns."""
    entry = _get_config_entry(hass)
    if not entry:
        return

    try:
        result = await fetch_devices(hass, entry)
    except SwitchBotApiError:
        _LOGGER.warning("Could not fetch SwitchBot device list for service cache")
        return

    device_map: dict[str, dict[str, Any]] = {}
    for device in result["devices"]:
        label = f"{device['device_name']} [{device['device_type']}]"
        device_map[label] = device

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_DEVICES] = result["devices"]
    hass.data[DOMAIN][DATA_DEVICE_MAP] = device_map
    hass.data[DOMAIN][DATA_CACHE_UPDATED_UTC] = datetime.now(timezone.utc).isoformat()
    hass.data[DOMAIN][DATA_CACHE_DEVICE_COUNT] = len(device_map)

    _LOGGER.debug(
        "Cached %s SwitchBot devices for service selectors", len(device_map)
    )


@callback
def _get_cached_device_map(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return the cached device_name->device_info map."""
    return hass.data.get(DOMAIN, {}).get(DATA_DEVICE_MAP, {})


@callback
def _resolve_device(
    hass: HomeAssistant, call_data: dict[str, Any]
) -> dict[str, Any]:
    """Resolve device_name to a full device record, or fall back to device_id."""
    device_name = call_data.get(ATTR_DEVICE_NAME)
    device_id = call_data.get(ATTR_DEVICE_ID)

    if device_name:
        device_map = _get_cached_device_map(hass)
        device = device_map.get(device_name)
        if device:
            return device
        for label, dev in device_map.items():
            if dev["device_name"] == device_name:
                return dev
        raise ServiceValidationError(
            f"Device '{device_name}' not found. "
            "Re-open the service to refresh the device list, or use device_id directly."
        )

    if device_id:
        cached_devices = hass.data.get(DOMAIN, {}).get(DATA_DEVICES, [])
        for dev in cached_devices:
            if dev["device_id"] == device_id:
                return dev
        return {
            "device_id": device_id,
            "device_name": device_id,
            "device_type": "Unknown",
            "is_infrared": device_id.startswith("02-") or device_id.startswith("03-"),
        }

    raise ServiceValidationError(
        "Either device_name or device_id must be provided"
    )


def _resolve_command(
    device: dict[str, Any], call_data: dict[str, Any]
) -> tuple[str, str | dict, str]:
    """Determine command, parameter, and command_type from call data and device type.

    Returns (command, parameter, command_type).
    """
    device_type = device.get("device_type", "Unknown")
    is_infrared = device.get("is_infrared", False)

    commands = get_commands_for_device_type(device_type, is_infrared=is_infrared)

    raw_command = call_data.get(ATTR_COMMAND, "")
    if raw_command and " \u2014 " in raw_command:
        raw_command = raw_command.split(" \u2014 ")[0].strip()

    if not raw_command:
        raw_command = "turnOn"

    cmd_def: CommandDef | None = None
    for c in commands:
        if c.command == raw_command:
            cmd_def = c
            break

    command_type = call_data.get(ATTR_COMMAND_TYPE, "")
    if cmd_def:
        command_type = cmd_def.command_type
    elif is_infrared and device_type == "Others":
        command_type = "customize"
    elif not command_type:
        command_type = "command"

    raw_parameter = call_data.get(ATTR_PARAMETER)
    if raw_parameter and isinstance(raw_parameter, str) and " \u2014 " in raw_parameter:
        raw_parameter = raw_parameter.split(" \u2014 ")[0].strip()

    if raw_parameter is None or raw_parameter == "":
        if cmd_def and cmd_def.parameter:
            raw_parameter = cmd_def.parameter
        else:
            raw_parameter = "default"

    parameter: str | dict = raw_parameter
    if isinstance(raw_parameter, str) and raw_parameter.startswith("{"):
        try:
            parameter = json.loads(raw_parameter)
        except (json.JSONDecodeError, ValueError):
            parameter = raw_parameter

    return raw_command, parameter, command_type


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

    await async_refresh_device_cache(hass)

    _LOGGER.debug("Fetched %s SwitchBot devices", result["device_count"])
    return result


async def async_get_auth_headers(call: ServiceCall) -> ServiceResponse:
    """Generate a fresh set of SwitchBot auth headers."""
    hass = call.hass
    entry = _get_config_entry(hass)
    if not entry:
        raise ServiceValidationError("No SwitchBot API configuration found")

    token = entry.data[CONF_TOKEN]
    secret = entry.data[CONF_SECRET]
    auth = generate_auth_payload(token, secret, ttl_seconds=AUTH_HEADER_TTL_SECONDS)

    _LOGGER.debug("Generated fresh SwitchBot auth headers")
    return auth


async def async_send_command(call: ServiceCall) -> ServiceResponse | None:
    """Send a command to a SwitchBot device."""
    hass = call.hass
    entry = _get_config_entry(hass)
    if not entry:
        raise ServiceValidationError("No SwitchBot API configuration found")

    device = _resolve_device(hass, call.data)
    device_id = device["device_id"]

    if not device_id:
        raise ServiceValidationError("Could not determine device ID")

    command, parameter, command_type = _resolve_command(device, call.data)

    payload: dict[str, Any] = {
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
            "device_name": device.get("device_name", device_id),
            "device_type": device.get("device_type", "Unknown"),
            "command": command,
            "parameter": parameter if isinstance(parameter, str) else json.dumps(parameter),
            "command_type": command_type,
            "body": body,
        }

    _LOGGER.debug(
        "SwitchBot command '%s' sent to %s (%s)", command, device_id, device.get("device_name")
    )
    return None


def _get_config_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Get the first SwitchBot API config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _build_send_command_schema(hass: HomeAssistant) -> vol.Schema:
    """Build the send_command schema with dynamic device list."""
    device_map = _get_cached_device_map(hass)
    device_names = sorted(device_map.keys()) if device_map else []

    schema_dict: dict[Any, Any] = {}

    if device_names:
        schema_dict[vol.Optional(ATTR_DEVICE_NAME)] = vol.In(device_names)
        schema_dict[vol.Optional(ATTR_DEVICE_ID)] = str
    else:
        schema_dict[vol.Required(ATTR_DEVICE_ID)] = str

    schema_dict[vol.Optional(ATTR_COMMAND, default="")] = str
    schema_dict[vol.Optional(ATTR_PARAMETER, default="")] = vol.Any(str, dict)
    schema_dict[vol.Optional(ATTR_COMMAND_TYPE, default="")] = str

    return vol.Schema(schema_dict)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register SwitchBot API services."""
    if not hass.services.has_service(DOMAIN, SERVICE_GET_DEVICES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_DEVICES,
            async_get_devices,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_GET_AUTH_HEADERS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_AUTH_HEADERS,
            async_get_auth_headers,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_COMMAND,
            async_send_command,
            schema=_build_send_command_schema(hass),
            supports_response=SupportsResponse.OPTIONAL,
        )


async def async_reregister_send_command(hass: HomeAssistant) -> None:
    """Re-register the send_command service with a refreshed schema."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_send_command,
        schema=_build_send_command_schema(hass),
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload registered services when no config entries remain."""
    if any(
        entry.state is ConfigEntryState.LOADED
        for entry in hass.config_entries.async_entries(DOMAIN)
    ):
        return

    for service in (SERVICE_GET_DEVICES, SERVICE_GET_AUTH_HEADERS, SERVICE_SEND_COMMAND):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

    hass.data.pop(DOMAIN, None)
