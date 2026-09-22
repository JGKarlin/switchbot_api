"""Turn the cached device list into generated Home Assistant actions.

Pure functions only; the Home Assistant registration wrapper lives in
services.py so that this module stays unit-testable without HA installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

import yaml

from .command_types import CommandDef, ParamField
from .device_commands import get_commands_for_device_type

CUSTOM_BUTTON_SUFFIX = " (custom button)"


@dataclass(frozen=True)
class GeneratedService:
    """One action to register and describe in services.yaml."""

    name: str
    title: str
    description: str
    device_id: str
    device_name: str
    device_type: str
    is_infrared: bool
    commands: tuple[CommandDef, ...] = ()
    command_def: CommandDef | None = None


def slugify(text: str) -> str:
    """Lowercase ASCII slug suitable for a Home Assistant service name."""
    lowered = text.lower()
    # Drop apostrophes/quotes outright rather than treating them as word
    # separators, so "Bob's TV" slugs to "bobs_tv" and not "bob_s_tv".
    lowered = re.sub(r"['‘’\"“”]", "", lowered)
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or "device"


def _custom_button_commands(names: Iterable[str]) -> tuple[CommandDef, ...]:
    return tuple(
        CommandDef(
            command=name,
            label=f"{name}{CUSTOM_BUTTON_SUFFIX}",
            description="Custom button configured in the SwitchBot app.",
            command_type="customize",
            parameter="default",
            encoding="none",
        )
        for name in names
    )


def _unique(base: str, taken: set[str], device_id: str) -> str:
    if base not in taken:
        return base
    suffix = slugify(device_id)[-8:] or "dup"
    candidate = f"{base}_{suffix}"
    counter = 2
    while candidate in taken:
        candidate = f"{base}_{suffix}_{counter}"
        counter += 1
    return candidate


def build_services(
    devices: Iterable[Mapping[str, Any]],
    *,
    ir_buttons: Mapping[str, list[str]] | None = None,
    existing_aliases: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[list[GeneratedService], dict[str, dict[str, Any]]]:
    """Build the generated action set and the refreshed alias map.

    Each alias record is `{"device_id": ..., "command": ...}`, where
    `command` is `None` for a dropdown action or the raw command name for a
    parameterized one. Recording the command, not just the device, lets a
    restored historical slug come back as the *same kind* of action it used
    to be -- restoring it from the device's dropdown unconditionally would
    silently strip the fields a parameterized automation depends on.
    """
    ir_buttons = ir_buttons or {}
    device_list = list(devices)
    live_ids = {d["device_id"] for d in device_list}

    services: list[GeneratedService] = []
    aliases: dict[str, str] = {}
    taken: set[str] = set()

    for device in device_list:
        device_id = device["device_id"]
        device_name = device.get("device_name") or device_id
        device_type = device.get("device_type") or "Unknown"
        is_infrared = bool(device.get("is_infrared"))

        # Hubs, meters, cameras and the Remote expose no commands at all.
        # An unknown physical type still gets a free-form action so a newly
        # released SwitchBot device is never dead, and every IR remote gets one
        # because custom buttons can be typed inline.
        if _has_no_commands(device_type):
            continue

        standard = tuple(
            get_commands_for_device_type(device_type, is_infrared=is_infrared)
        )
        custom = _custom_button_commands(ir_buttons.get(device_id, ()))

        all_commands = standard + custom
        simple = tuple(c for c in all_commands if not c.fields)
        parameterized = tuple(c for c in all_commands if c.fields)

        base_slug = _unique(slugify(device_name), taken, device_id)
        taken.add(base_slug)
        aliases[base_slug] = {"device_id": device_id, "command": None}

        services.append(
            GeneratedService(
                name=base_slug,
                title=f"SwitchBot: {device_name}",
                description=f"Control {device_name} ({device_type}).",
                device_id=device_id,
                device_name=device_name,
                device_type=device_type,
                is_infrared=is_infrared,
                commands=simple,
            )
        )

        for command in parameterized:
            label = command.display_label
            name = _unique(f"{base_slug}_{slugify(label)}", taken, device_id)
            taken.add(name)
            aliases[name] = {"device_id": device_id, "command": command.command}
            services.append(
                GeneratedService(
                    name=name,
                    title=f"SwitchBot: {device_name} - {label}",
                    description=command.description
                    or f"{label} on {device_name}.",
                    device_id=device_id,
                    device_name=device_name,
                    device_type=device_type,
                    is_infrared=is_infrared,
                    command_def=command,
                )
            )

    for slug, record in (existing_aliases or {}).items():
        device_id = record["device_id"]
        command = record.get("command")

        if device_id not in live_ids:
            continue  # the device is gone; the alias must not survive it

        if slug in aliases:
            # A device already claims this slug in the fresh generation --
            # either the same device regenerated it identically (nothing to
            # add), or a *different* device now owns it. Restoring the
            # historical mapping in the second case would silently redirect
            # an old automation to someone else's device, so both cases are
            # dropped the same way: the freshly generated entry wins.
            continue

        source = next(
            (
                s
                for s in services
                if s.device_id == device_id
                and (s.command_def.command if s.command_def else None) == command
            ),
            None,
        )
        if source is None:
            continue  # the recorded command no longer exists for this device

        aliases[slug] = {"device_id": device_id, "command": command}
        services.append(replace(source, name=slug))

    return services, aliases


def _has_no_commands(device_type: str) -> bool:
    """True for hubs, meters, cameras and other command-less device types."""
    from .command_overlay import DEVICE_TYPE_ALIASES

    return DEVICE_TYPE_ALIASES.get(device_type) in ("_hub", "_no_commands")


SEND_COMMAND_EXAMPLES = {
    "device_id": "C271111EC0AB",
    "command": "turnOn",
    "parameter": "default",
    "command_type": "command",
}


def _selector_for(field: ParamField) -> dict[str, Any]:
    if field.kind == "number":
        number: dict[str, Any] = {}
        if field.minimum is not None:
            number["min"] = field.minimum
        if field.maximum is not None:
            number["max"] = field.maximum
        if field.unit:
            number["unit_of_measurement"] = field.unit
        number["mode"] = (
            "slider"
            if field.minimum is not None and field.maximum is not None
            else "box"
        )
        return {"number": number}
    if field.kind == "select":
        return {
            "select": {
                "options": [
                    {"label": label, "value": value} for value, label in field.options
                ]
            }
        }
    if field.kind == "boolean":
        return {"boolean": None}
    return {"text": None}


def _field_block(field: ParamField) -> dict[str, Any]:
    block: dict[str, Any] = {"name": field.label}
    if field.help:
        block["description"] = field.help
    block["required"] = field.default is None
    if field.default is not None:
        block["default"] = field.default
    block["selector"] = _selector_for(field)
    return block


def _command_field(service: GeneratedService) -> dict[str, Any]:
    if not service.commands:
        help_text = (
            "Name of a custom button configured in the SwitchBot app "
            "(case-sensitive)."
            if service.is_infrared
            else "Raw SwitchBot command name."
        )
        return {
            "name": "Command",
            "description": help_text,
            "required": True,
            "selector": {"text": None},
        }

    select: dict[str, Any] = {
        "options": [
            {"label": c.display_label, "value": c.command} for c in service.commands
        ]
    }
    if service.is_infrared:
        select["custom_value"] = True
    return {
        "name": "Command",
        "description": "What this device should do.",
        "required": True,
        "selector": {"select": select},
    }


def _service_block(service: GeneratedService) -> dict[str, Any]:
    block: dict[str, Any] = {
        "name": service.title,
        "description": service.description,
        "fields": {},
    }
    if service.command_def is None:
        block["fields"]["command"] = _command_field(service)
    else:
        for field in service.command_def.fields:
            block["fields"][field.key] = _field_block(field)
    return block


def _static_services(device_labels: list[str]) -> dict[str, Any]:
    if device_labels:
        device_selector: dict[str, Any] = {"select": {"options": list(device_labels)}}
    else:
        device_selector = {"text": None}

    fields: dict[str, Any] = {
        "device_name": {"required": False, "selector": device_selector}
    }
    for key in ("device_id", "command", "parameter", "command_type"):
        fields[key] = {
            "required": False,
            "example": SEND_COMMAND_EXAMPLES[key],
            "selector": {"text": None},
        }

    return {
        "get_devices": {},
        "get_auth_headers": {},
        "send_command": {"fields": fields},
    }


def render_services_yaml(
    generated: Iterable[GeneratedService], *, device_labels: list[str]
) -> str:
    """Render the complete services.yaml, static actions first."""
    document: dict[str, Any] = _static_services(device_labels)
    for service in sorted(generated, key=lambda s: s.name):
        document[service.name] = _service_block(service)

    header = (
        "# GENERATED FILE - regenerated whenever the SwitchBot device list is\n"
        "# refreshed. Hand edits are overwritten.\n"
    )
    body = yaml.safe_dump(
        document, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return header + body
