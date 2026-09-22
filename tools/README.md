# Build-time tooling

These scripts are **not** used by Home Assistant at runtime. They ship with the
integration only because `hacs.json` sets `content_in_root: true`.

## Regenerating the command index

    python3 tools/generate_command_index.py

Fetches every `devices/**/*.md` from
[OpenWonderLabs/SwitchBotAPI](https://github.com/OpenWonderLabs/SwitchBotAPI),
parses each `## Control Commands` table, derives typed parameter fields, and
rewrites `command_index.py`. Review the diff before committing.

Use `--dry-run` to print the report without writing.

A `DeviceTypeConflict` means a device's declared type and its command-table type
disagree and no alias reconciles them. Add the pair to `RECONCILED_TYPES` in
`tools/doc_parser.py`. The generator fails rather than silently dropping a
device type.

Hand-written labels and schema fixes belong in `command_overlay.py`, which is
merged over the generated data and survives regeneration. The generator's report
lists every command that fell back to a plain text field — those are the
candidates.

## Tests

    python3 -m venv .venv
    .venv/bin/pip install pytest pyyaml
    .venv/bin/pytest

Tests run without Home Assistant installed. Modules that import
`homeassistant` (`services.py`, `config_flow.py`, `__init__.py`, `button.py`,
`sensor.py`, `api.py`) are verified manually in a live instance.
