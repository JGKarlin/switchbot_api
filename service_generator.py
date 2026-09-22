"""Turn the cached device list into generated Home Assistant actions.

Pure functions only; the Home Assistant registration wrapper lives in
services.py so that this module stays unit-testable without HA installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from .command_types import CommandDef
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
    existing_aliases: Mapping[str, str] | None = None,
) -> tuple[list[GeneratedService], dict[str, str]]:
    """Build the generated action set and the refreshed slug->device_id map."""
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
        aliases[base_slug] = device_id

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
            aliases[name] = device_id
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

    for slug, device_id in (existing_aliases or {}).items():
        if slug in aliases or device_id not in live_ids:
            continue
        source = next(
            (s for s in services if s.device_id == device_id and s.command_def is None),
            None,
        )
        if source is None:
            continue
        aliases[slug] = device_id
        services.append(replace(source, name=slug))

    return services, aliases


def _has_no_commands(device_type: str) -> bool:
    """True for hubs, meters, cameras and other command-less device types."""
    from .command_overlay import DEVICE_TYPE_ALIASES

    return DEVICE_TYPE_ALIASES.get(device_type) in ("_hub", "_no_commands")
