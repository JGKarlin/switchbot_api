"""Generate command_index.py from the SwitchBot API documentation.

Usage:
    python3 tools/generate_command_index.py            # fetch and write
    python3 tools/generate_command_index.py --dry-run  # report only

Build-time only. Never imported by Home Assistant.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import doc_parser  # noqa: E402
import schema_derive  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "command_index.py"

TREE_URL = (
    "https://api.github.com/repos/OpenWonderLabs/SwitchBotAPI/git/trees/main"
    "?recursive=1"
)
RAW_BASE = "https://raw.githubusercontent.com/OpenWonderLabs/SwitchBotAPI/main/"
IR_DOC = "devices/others/virtual-infrared-remote-devices.md"

# Upstream writes placeholders, not command names, for user-defined buttons.
PLACEHOLDER_COMMAND_RE = re.compile(r"^\{.*\}$")

HEADER = '''"""SwitchBot device command index.

GENERATED FILE - do not edit by hand.
Regenerate with: python3 tools/generate_command_index.py

Source: https://github.com/OpenWonderLabs/SwitchBotAPI
Hand-written labels and schema fixes belong in command_overlay.py, which is
merged over this data and survives regeneration.
"""

from __future__ import annotations

from .command_types import CommandDef, ParamField

'''


def _fetch(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "switchbot_api-index-generator"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def list_device_docs() -> list[str]:
    """Return every devices/**/*.md path in the upstream repository."""
    tree = json.loads(_fetch(TREE_URL))
    return sorted(
        item["path"]
        for item in tree.get("tree", [])
        if item["path"].startswith("devices/") and item["path"].endswith(".md")
    )


def _render_entries(index: dict[str, list]) -> str:
    lines = []
    for device_type in sorted(index):
        commands = index[device_type]
        lines.append(f"    {json.dumps(device_type)}: [")
        for command in commands:
            lines.append(f"        {command!r},")
        lines.append("    ],")
    return "\n".join(lines)


def _render_alias_entries(aliases: dict[str, str]) -> str:
    lines = []
    for declared in sorted(aliases):
        lines.append(f"    {json.dumps(declared)}: {json.dumps(aliases[declared])},")
    return "\n".join(lines)


def render_index_module(
    physical: dict[str, list],
    infrared: dict[str, list],
    aliases: dict[str, str] | None = None,
) -> str:
    """Render the generated module source."""
    aliases = aliases or {}
    return (
        HEADER
        + "COMMAND_INDEX: dict[str, list[CommandDef]] = {\n"
        + _render_entries(physical)
        + ("\n" if physical else "")
        + "}\n\n"
        + "IR_COMMAND_INDEX: dict[str, list[CommandDef]] = {\n"
        + _render_entries(infrared)
        + ("\n" if infrared else "")
        + "}\n\n"
        + "# Maps a deviceType spelling the /v1.1/devices API actually returns\n"
        + "# (the doc's declared type) to the spelling used as a COMMAND_INDEX /\n"
        + "# IR_COMMAND_INDEX key (the doc's Control Commands table spelling).\n"
        + "# Do not add both spellings as separate index keys -- look up a\n"
        + "# deviceType here first, and fall back to the raw value if absent.\n"
        + "GENERATED_TYPE_ALIASES: dict[str, str] = {\n"
        + _render_alias_entries(aliases)
        + ("\n" if aliases else "")
        + "}\n"
    )


def build_index() -> tuple[dict[str, list], dict[str, list], list[str], dict[str, str]]:
    """Fetch and parse every device doc.

    Returns (physical, infrared, fallbacks, aliases). `aliases` maps a doc's
    declared deviceType (the spelling the live API returns) to the spelling
    used as its COMMAND_INDEX key, for every doc where the two differ and
    RECONCILED_TYPES reconciles them. Losing the declared spelling would
    leave any device the API reports under that name with no commands at
    all, so the generator must emit the mapping rather than only using it to
    suppress the DeviceTypeConflict check.
    """
    physical: dict[str, list] = {}
    infrared: dict[str, list] = {}
    fallbacks: list[str] = []
    aliases: dict[str, str] = {}
    # Per-target, per-device-type set of (command, command_type) pairs already
    # emitted. Upstream sometimes documents the same device type across more
    # than one doc with byte-identical Control Commands tables (e.g. the two
    # Humidifier2 variants); scoping dedup to (target, device_type, pair)
    # drops exact repeats while still allowing the same command name to
    # appear for a different device type, or twice under different
    # command_type values within one device type.
    physical_seen: dict[str, set[tuple[str, str]]] = {}
    infrared_seen: dict[str, set[tuple[str, str]]] = {}

    paths = list_device_docs()
    print(f"fetched tree: {len(paths)} device docs")

    for path in paths:
        markdown = _fetch(RAW_BASE + path)
        rows = doc_parser.parse_control_commands(markdown)
        if not rows:
            continue

        target = infrared if path == IR_DOC else physical
        seen = infrared_seen if path == IR_DOC else physical_seen

        if path != IR_DOC:
            declared = doc_parser.extract_declared_device_type(markdown)
            if declared:
                table_types = {r.device_type for r in rows}
                doc_parser.check_device_type_agreement(declared, table_types)
                if declared not in table_types:
                    resolved = doc_parser.RECONCILED_TYPES.get(declared)
                    if resolved is not None:
                        aliases[declared] = resolved

        for row in rows:
            if PLACEHOLDER_COMMAND_RE.match(row.command):
                # Upstream lists "{user-defined button name}" as the only entry
                # for Others-type remotes. It is a placeholder, not a command;
                # real names come from the user via the options flow.
                continue
            for expanded in doc_parser.expand_device_types(row):
                command = schema_derive.derive_command(expanded)
                pair = (command.command, command.command_type)
                device_seen = seen.setdefault(expanded.device_type, set())
                if pair in device_seen:
                    continue
                device_seen.add(pair)
                if any(f.kind == "text" for f in command.fields):
                    fallbacks.append(f"{expanded.device_type}:{expanded.command}")
                target.setdefault(expanded.device_type, []).append(command)

    return physical, infrared, fallbacks, aliases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    physical, infrared, fallbacks, aliases = build_index()

    total = sum(len(v) for v in physical.values()) + sum(
        len(v) for v in infrared.values()
    )
    print(f"physical device types: {len(physical)}")
    print(f"infrared device types: {len(infrared)}")
    print(f"commands parsed:       {total}")
    print(f"auto-derived schemas:  {total - len(fallbacks)}")
    print(f"needs overlay:         {len(fallbacks)}")
    for item in sorted(fallbacks):
        print(f"  - {item}")
    print(f"type aliases:          {len(aliases)}")
    for declared in sorted(aliases):
        print(f"  - {declared!r} -> {aliases[declared]!r}")

    if args.dry_run:
        return 0

    OUTPUT.write_text(render_index_module(physical, infrared, aliases), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
