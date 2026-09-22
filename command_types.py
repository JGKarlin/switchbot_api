"""Parameter schema and wire encoding for SwitchBot commands.

Pure stdlib. Imported by command_index, command_overlay and device_commands,
and exercised by tests with no Home Assistant installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class ParameterError(ValueError):
    """Field values cannot be encoded into an API parameter."""


@dataclass(frozen=True)
class ParamField:
    """One user-supplied input that feeds a command's parameter."""

    key: str
    label: str
    kind: str = "text"  # number | select | boolean | text
    required: bool = True
    default: str | None = None
    minimum: int | None = None
    maximum: int | None = None
    unit: str | None = None
    options: tuple[tuple[str, str], ...] = ()  # (value, label)
    value_type: str = "auto"  # auto | str | int | bool
    help: str = ""


@dataclass(frozen=True)
class CommandDef:
    """A single command supported by a device type."""

    command: str
    label: str = ""
    description: str = ""
    command_type: str = "command"
    parameter: str = "default"
    fields: tuple[ParamField, ...] = ()
    encoding: str = "none"

    @property
    def display_label(self) -> str:
        """Human label, falling back to the raw command name."""
        return self.label or self.command


def resolve_values(
    command_def: CommandDef, supplied: Mapping[str, Any]
) -> dict[str, Any]:
    """Fill every field from the supplied values or its default.

    A field with neither is an error: encoding it as an empty positional part
    would send something like ",ff,80" and fail opaquely at the API.
    """
    resolved: dict[str, Any] = {}
    for fld in command_def.fields:
        raw = supplied.get(fld.key)
        if raw is None or raw == "":
            if fld.default is None:
                name = command_def.display_label
                raise ParameterError(
                    f"'{fld.label}' is required for {name} and has no default"
                )
            raw = fld.default
        resolved[fld.key] = raw
    return resolved


def _as_bool_text(raw: Any) -> str:
    if isinstance(raw, bool):
        return "true" if raw else "false"
    return "true" if str(raw).strip().lower() in ("true", "1", "yes", "on") else "false"


def _coerce_json_value(fld: ParamField, raw: Any) -> Any:
    if fld.value_type == "str":
        return str(raw)
    if fld.value_type == "int":
        try:
            return int(raw)
        except (ValueError, TypeError) as e:
            raise ParameterError(
                f"'{fld.label}' must be a number, got {raw!r}"
            )
    if fld.value_type == "bool":
        return _as_bool_text(raw) == "true"
    text = str(raw)
    if text.lstrip("-").isdigit():
        try:
            return int(text)
        except (ValueError, TypeError) as e:
            raise ParameterError(
                f"'{fld.label}' must be a number, got {raw!r}"
            )
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return text


def _wire_text(fld: ParamField, raw: Any) -> str:
    if fld.value_type == "bool" or fld.kind == "boolean":
        return _as_bool_text(raw)
    return str(raw)


def encode_parameter(
    command_def: CommandDef, supplied: Mapping[str, Any]
) -> str | dict[str, Any]:
    """Build the API's `parameter` value from user-supplied field values."""
    encoding = command_def.encoding

    if encoding == "none" or not command_def.fields:
        return command_def.parameter or "default"

    resolved = resolve_values(command_def, supplied)

    if encoding == "csv":
        return ",".join(
            _wire_text(fld, resolved[fld.key]) for fld in command_def.fields
        )

    if encoding == "json":
        return {
            fld.key: _coerce_json_value(fld, resolved[fld.key])
            for fld in command_def.fields
        }

    if encoding == "scalar":
        fld = command_def.fields[0]
        return _wire_text(fld, resolved[fld.key])

    raise ParameterError(f"unknown encoding {encoding!r}")
