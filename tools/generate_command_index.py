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


def render_index_module(physical: dict[str, list], infrared: dict[str, list]) -> str:
    """Render the generated module source."""
    return (
        HEADER
        + "COMMAND_INDEX: dict[str, list[CommandDef]] = {\n"
        + _render_entries(physical)
        + ("\n" if physical else "")
        + "}\n\n"
        + "IR_COMMAND_INDEX: dict[str, list[CommandDef]] = {\n"
        + _render_entries(infrared)
        + ("\n" if infrared else "")
        + "}\n"
    )


def build_index() -> tuple[dict[str, list], dict[str, list], list[str]]:
    """Fetch and parse every device doc. Returns (physical, infrared, fallbacks)."""
    physical: dict[str, list] = {}
    infrared: dict[str, list] = {}
    fallbacks: list[str] = []

    paths = list_device_docs()
    print(f"fetched tree: {len(paths)} device docs")

    for path in paths:
        markdown = _fetch(RAW_BASE + path)
        rows = doc_parser.parse_control_commands(markdown)
        if not rows:
            continue

        target = infrared if path == IR_DOC else physical

        if path != IR_DOC:
            declared = doc_parser.extract_declared_device_type(markdown)
            if declared:
                doc_parser.check_device_type_agreement(
                    declared, {r.device_type for r in rows}
                )

        for row in rows:
            if PLACEHOLDER_COMMAND_RE.match(row.command):
                # Upstream lists "{user-defined button name}" as the only entry
                # for Others-type remotes. It is a placeholder, not a command;
                # real names come from the user via the options flow.
                continue
            for expanded in doc_parser.expand_device_types(row):
                command = schema_derive.derive_command(expanded)
                if any(f.kind == "text" for f in command.fields):
                    fallbacks.append(f"{expanded.device_type}:{expanded.command}")
                target.setdefault(expanded.device_type, []).append(command)

    return physical, infrared, fallbacks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    physical, infrared, fallbacks = build_index()

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

    if args.dry_run:
        return 0

    OUTPUT.write_text(render_index_module(physical, infrared), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
