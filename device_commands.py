"""Lookup layer over the generated command index and the hand-written overlay.

Public API is unchanged from 3.x for get_commands_for_device_type() and
get_parameter_label(); find_command() and resolve_command_type() are new.

Physical device type resolution order (see _resolve_physical_type):
1. DEVICE_TYPE_ALIASES (hand-written, command_overlay.py) -- deliberate
   _hub / _no_commands decisions and hand-chosen redirects such as
   "Evaporative Humidifier" -> "Humidifier2".
2. GENERATED_TYPE_ALIASES (command_index.py) -- maps a deviceType spelling
   the SwitchBot API actually returns (e.g. "Smart Lock") to the spelling
   used in the docs' Control Commands table (e.g. "Lock").
3. The device type as a direct key into COMMAND_INDEX.
"""

from __future__ import annotations

from dataclasses import replace

from .command_index import COMMAND_INDEX, GENERATED_TYPE_ALIASES, IR_COMMAND_INDEX
from .command_overlay import (
    COMMAND_OVERLAY,
    DEVICE_TYPE_ALIASES,
    PARAMETER_OPTION_LABELS,
)
from .command_types import CommandDef, ParamField

# Commands the upstream IR table lists for every remote type except Others.
# Must match tools/doc_parser.ALL_IR_EXCEPT_OTHERS -- it is defined
# independently there (build-time parser) and here (runtime lookup); if they
# ever drift, infrared devices silently lose their standard commands.
ALL_IR_EXCEPT_OTHERS = "_all_ir_except_others"

__all__ = [
    "CommandDef",
    "ParamField",
    "get_commands_for_device_type",
    "get_parameter_label",
    "find_command",
    "resolve_command_type",
]


def _apply_overlay(device_type: str, command: CommandDef) -> CommandDef:
    patch = COMMAND_OVERLAY.get(f"{device_type}:{command.command}")
    return replace(command, **patch) if patch else command


def _normalize_ir_type(device_type: str) -> str:
    """Strip the DIY prefix SwitchBot uses for DIY-learned remotes."""
    if device_type.startswith("DIY "):
        return device_type[4:].strip()
    return device_type


def _resolve_physical_type(device_type: str) -> str:
    """Resolve a physical deviceType to its COMMAND_INDEX key.

    Hand-written aliases win first, then generated aliases, then the device
    type itself. See the module docstring for why the order matters.
    """
    if device_type in DEVICE_TYPE_ALIASES:
        return DEVICE_TYPE_ALIASES[device_type]
    if device_type in GENERATED_TYPE_ALIASES:
        return GENERATED_TYPE_ALIASES[device_type]
    return device_type


def get_commands_for_device_type(
    device_type: str, *, is_infrared: bool = False
) -> list[CommandDef]:
    """Return every command available for a device type, overlay applied."""
    if is_infrared:
        resolved = _normalize_ir_type(device_type)
        if resolved not in IR_COMMAND_INDEX:
            return []
        commands = list(IR_COMMAND_INDEX.get(ALL_IR_EXCEPT_OTHERS, []))
        commands += IR_COMMAND_INDEX[resolved]
        return [_apply_overlay(resolved, c) for c in commands]

    resolved = _resolve_physical_type(device_type)
    if resolved in ("_hub", "_no_commands"):
        return []
    return [_apply_overlay(resolved, c) for c in COMMAND_INDEX.get(resolved, [])]


def find_command(
    device_type: str, command: str, *, is_infrared: bool = False
) -> CommandDef | None:
    """Return the CommandDef for an exact command name, or None."""
    for candidate in get_commands_for_device_type(
        device_type, is_infrared=is_infrared
    ):
        if candidate.command == command:
            return candidate
    return None


def resolve_command_type(
    device_type: str,
    command: str,
    *,
    is_infrared: bool = False,
    custom_buttons: tuple[str, ...] = (),
) -> str:
    """Decide the API's commandType for a chosen command.

    Custom IR button names are matched verbatim; upstream documents them as
    case-sensitive. A custom button on ANY remote type requires
    commandType=customize, not only on Others-type remotes.

    For infrared devices, a command that is not a declared custom button is
    treated as a standard command (commandType=command) whenever the remote
    type itself is a recognized typed remote (present in IR_COMMAND_INDEX),
    even if that exact command name is not one of its listed commands --
    only remote types with no standard command set at all (Others, or an
    unrecognized type) fall back to commandType=customize.
    """
    if not is_infrared:
        found = find_command(device_type, command)
        return found.command_type if found else "command"

    if command in tuple(custom_buttons):
        return "customize"

    found = find_command(device_type, command, is_infrared=True)
    if found is not None:
        return found.command_type

    resolved = _normalize_ir_type(device_type)
    if resolved in IR_COMMAND_INDEX:
        return "command"
    return "customize"


def get_parameter_label(command: str, value: str, device_type: str = "") -> str:
    """Return a human-readable label for a parameter option value."""
    device_key = f"{command}:{device_type}"
    if device_key in PARAMETER_OPTION_LABELS:
        return PARAMETER_OPTION_LABELS[device_key].get(value, value)
    if command in PARAMETER_OPTION_LABELS:
        return PARAMETER_OPTION_LABELS[command].get(value, value)
    return value
