"""Services for the SwitchBot API integration."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
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
from .command_types import ParameterError, encode_parameter
from .const import (
    AUTH_HEADER_TTL_SECONDS,
    CONF_SECRET,
    CONF_TOKEN,
    DOMAIN,
)
from .device_commands import (
    CommandDef,
    find_command,
    get_commands_for_device_type,
    resolve_command_type,
)
from .service_generator import (
    CONF_IR_BUTTONS,
    GeneratedService,
    build_services,
    render_services_yaml,
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
DATA_GENERATED_SERVICES = "generated_services"

CONF_SERVICE_ALIASES = "service_aliases"


def get_ir_buttons(entry: ConfigEntry) -> dict[str, list[str]]:
    """Registered custom IR button names, keyed by device ID."""
    return dict(entry.options.get(CONF_IR_BUTTONS, {}))


async def _async_remember_ir_button(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str, command: str
) -> None:
    """Remember a custom button name the API accepted, then schedule a regen.

    Regeneration is scheduled with async_create_task rather than awaited:
    this runs from inside a generated service handler that is still
    executing, and async_regenerate_services() unregisters and re-registers
    the generated service set. Awaiting it here would remove the very
    service call currently in flight.
    """
    buttons = get_ir_buttons(entry)
    known = list(buttons.get(device_id, []))
    if command in known:
        return

    known.append(command)
    buttons[device_id] = known
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_IR_BUTTONS: buttons}
    )
    _LOGGER.debug("Learned custom IR button '%s' for %s", command, device_id)
    hass.async_create_task(async_regenerate_services(hass))


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


def _write_services_yaml_blocking(content: str) -> None:
    """Write services.yaml. Runs in an executor -- never on the event loop."""
    services_path = Path(__file__).parent / "services.yaml"
    try:
        services_path.write_text(content, encoding="utf-8")
    except OSError:
        _LOGGER.warning("Could not write services.yaml for generated actions")


async def async_regenerate_services(hass: HomeAssistant) -> None:
    """Rebuild the generated action set, rewrite services.yaml, re-register."""
    entry = _get_config_entry(hass)
    if not entry:
        return

    devices = hass.data.get(DOMAIN, {}).get(DATA_DEVICES, [])
    device_map = _get_cached_device_map(hass)

    generated, aliases = build_services(
        devices,
        ir_buttons=get_ir_buttons(entry),
        existing_aliases=entry.options.get(CONF_SERVICE_ALIASES, {}),
    )

    if aliases != entry.options.get(CONF_SERVICE_ALIASES, {}):
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_SERVICE_ALIASES: aliases}
        )

    content = render_services_yaml(
        generated, device_labels=sorted(device_map.keys())
    )
    await hass.async_add_executor_job(_write_services_yaml_blocking, content)

    _register_generated_services(hass, entry, generated)


@callback
def _register_generated_services(
    hass: HomeAssistant,
    entry: ConfigEntry,
    generated: list[GeneratedService],
) -> None:
    """Register one handler per generated action, removing stale ones first."""
    previous: set[str] = set(hass.data.get(DOMAIN, {}).get(DATA_GENERATED_SERVICES, ()))
    current = {service.name for service in generated}

    for name in previous - current:
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)

    for service in generated:
        if hass.services.has_service(DOMAIN, service.name):
            hass.services.async_remove(DOMAIN, service.name)
        hass.services.async_register(
            DOMAIN,
            service.name,
            _make_generated_handler(hass, service),
            schema=_generated_schema(service),
            supports_response=SupportsResponse.OPTIONAL,
        )

    hass.data.setdefault(DOMAIN, {})[DATA_GENERATED_SERVICES] = sorted(current)


def _generated_schema(service: GeneratedService) -> vol.Schema:
    """Permissive schema; the handler validates against the CommandDef."""
    if service.command_def is None:
        return vol.Schema({vol.Required(ATTR_COMMAND): str})
    return vol.Schema(
        {
            vol.Optional(field.key): vol.Any(str, int, float, bool)
            for field in service.command_def.fields
        }
    )


def _make_generated_handler(hass: HomeAssistant, service: GeneratedService):
    """Build the handler closure for one generated action."""

    async def _handler(call: ServiceCall) -> ServiceResponse | None:
        entry = _get_config_entry(hass)
        if not entry:
            raise ServiceValidationError("No SwitchBot API configuration found")

        device = {
            "device_id": service.device_id,
            "device_name": service.device_name,
            "device_type": service.device_type,
            "is_infrared": service.is_infrared,
        }

        if service.command_def is None:
            command = call.data[ATTR_COMMAND]
            command_def = find_command(
                service.device_type, command, is_infrared=service.is_infrared
            )
            parameter: str | dict = "default"
            if command_def is not None:
                parameter = encode_parameter(command_def, {})
        else:
            command_def = service.command_def
            command = command_def.command
            try:
                parameter = encode_parameter(command_def, call.data)
            except ParameterError as exc:
                raise ServiceValidationError(str(exc)) from exc

        command_type = resolve_command_type(
            service.device_type,
            command,
            is_infrared=service.is_infrared,
            custom_buttons=tuple(get_ir_buttons(entry).get(service.device_id, ())),
        )

        body = await _async_send(
            hass, entry, device, command, parameter, command_type
        )

        if call.return_response:
            return {
                "device_id": service.device_id,
                "device_name": service.device_name,
                "device_type": service.device_type,
                "command": command,
                "parameter": parameter
                if isinstance(parameter, str)
                else json.dumps(parameter),
                "command_type": command_type,
                "body": body,
            }
        return None

    return _handler


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
    device: dict[str, Any],
    call_data: dict[str, Any],
    *,
    custom_buttons: tuple[str, ...] = (),
) -> tuple[str, str | dict, str]:
    """Determine command, parameter, and command_type from call data and device type.

    An explicit command_type in call_data wins for physical devices --
    send_command is the documented raw escape hatch, and a wrong explicit
    value there should surface as a clear API error rather than be silently
    overridden. Infrared devices are the one exception: see the comment
    above the command_type block below.

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

    resolved_type = resolve_command_type(
        device_type,
        raw_command,
        is_infrared=is_infrared,
        custom_buttons=tuple(custom_buttons),
    )
    explicit_type = call_data.get(ATTR_COMMAND_TYPE, "")

    # Infrared "customize" wins even over an explicit command_type.
    # Pre-4.0.0 behaviour (see 8acb267:services.py:240-247) unconditionally
    # forced commandType=customize for infrared Others devices: the API
    # rejects a typed/custom IR button name as a standard "command", but
    # the send_command README example shows command_type: command, so an
    # automation built from that example against an infrared remote's
    # custom button only ever worked because the old code silently
    # corrected the value. Making explicit-wins unconditional here would
    # turn that working automation into an opaque API error. Every other
    # device kind keeps explicit-wins (see the function docstring).
    if is_infrared and resolved_type == "customize":
        command_type = "customize"
    elif explicit_type:
        command_type = explicit_type
    else:
        command_type = resolved_type

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
    await async_regenerate_services(hass)

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


async def _async_send(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: dict[str, Any],
    command: str,
    parameter: str | dict,
    command_type: str,
) -> dict[str, Any]:
    """POST a command to a device. Shared by send_command and generated actions."""
    device_id = device["device_id"]
    if not device_id:
        raise ServiceValidationError("Could not determine device ID")

    payload: dict[str, Any] = {
        "command": command,
        "parameter": parameter,
        "commandType": command_type,
    }

    try:
        body = await async_request(
            hass,
            "POST",
            f"/devices/{device_id}/commands",
            entry.data[CONF_TOKEN],
            entry.data[CONF_SECRET],
            payload=payload,
        )
    except SwitchBotApiError as exc:
        raise ServiceValidationError(str(exc)) from exc

    if command_type == "customize":
        await _async_remember_ir_button(hass, entry, device_id, command)

    return body


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

    entry_buttons = get_ir_buttons(entry).get(device_id, [])
    command, parameter, command_type = _resolve_command(
        device, call.data, custom_buttons=entry_buttons
    )

    body = await _async_send(hass, entry, device, command, parameter, command_type)

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

    for name in hass.data.get(DOMAIN, {}).get(DATA_GENERATED_SERVICES, ()):
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)

    hass.data.pop(DOMAIN, None)
