"""Parse SwitchBot API documentation tables into command rows.

Build-time only. Never imported by Home Assistant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ALL_IR_EXCEPT_OTHERS = "_all_ir_except_others"

# Upstream documents the same device with different spellings in its
# device-list table and its command table. Each entry is
# declared_spelling -> the spelling used in the Control Commands table.
RECONCILED_TYPES: dict[str, str] = {
    "Curtain3": "Curtain 3",
    "WoCurtain3": "Curtain 3",
    "Humidifier2": "Humidifier2",
}

_SECTION_RE = re.compile(
    r"^##\s+Control Commands\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
)
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
_DECLARED_TYPE_RE = re.compile(r"device type\.\s*_([^_]+)_", re.IGNORECASE)


@dataclass(frozen=True)
class CommandRow:
    """One row of an upstream Control Commands table, as raw strings."""

    device_type: str
    command_type: str
    command: str
    parameter_spec: str
    description: str


class DeviceTypeConflict(Exception):
    """A device's declared type and its command-table type do not reconcile."""


def _clean(cell: str) -> str:
    """Normalize a markdown table cell to plain text."""
    text = cell.replace("<br />", " ").replace("<br/>", " ").replace("<br>", " ")
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_control_commands(markdown: str) -> list[CommandRow]:
    """Extract every row of the '## Control Commands' table."""
    section = _SECTION_RE.search(markdown)
    if not section:
        return []

    rows: list[CommandRow] = []
    last_device_type = ""
    seen_header = False

    for line in section.group(1).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if _SEPARATOR_RE.match(line):
            continue

        cells = [_clean(c) for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue

        if not seen_header:
            # The first table row is the header (deviceType | commandType | ...).
            seen_header = True
            if cells[0].lower().replace(" ", "") == "devicetype":
                continue

        device_type, command_type, command, parameter_spec, description = cells[:5]

        if not any((device_type, command_type, command)):
            continue  # upstream pads tables with fully empty rows
        if not command:
            continue

        if device_type:
            last_device_type = device_type
        else:
            device_type = last_device_type

        rows.append(
            CommandRow(
                device_type=device_type,
                command_type=command_type or "command",
                command=command,
                parameter_spec=parameter_spec,
                description=description,
            )
        )

    return rows


def expand_device_types(row: CommandRow) -> list[CommandRow]:
    """Split a row whose deviceType cell names several types."""
    raw = row.device_type.strip()
    if raw.lower().startswith("all home appliance types except others"):
        return [_replace_type(row, ALL_IR_EXCEPT_OTHERS)]
    if "," not in raw:
        return [row]
    return [_replace_type(row, part.strip()) for part in raw.split(",") if part.strip()]


def _replace_type(row: CommandRow, device_type: str) -> CommandRow:
    return CommandRow(
        device_type=device_type,
        command_type=row.command_type,
        command=row.command,
        parameter_spec=row.parameter_spec,
        description=row.description,
    )


def extract_declared_device_type(markdown: str) -> str | None:
    """Read the deviceType a doc declares in its Device List Information table."""
    match = _DECLARED_TYPE_RE.search(markdown)
    return match.group(1).strip() if match else None


def check_device_type_agreement(declared: str, table_types: set[str]) -> None:
    """Fail loudly when a doc's two device-type spellings do not reconcile.

    Silently dropping an unreconciled device type would produce an index that
    is quietly missing a whole device, which is worse than a failed build.
    """
    if declared in table_types:
        return
    if RECONCILED_TYPES.get(declared) in table_types:
        return
    raise DeviceTypeConflict(
        f"declared device type {declared!r} does not match command-table "
        f"types {sorted(table_types)!r}; add an entry to RECONCILED_TYPES"
    )
