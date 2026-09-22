# Friendly Auto-Generated Command UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one Home Assistant action per detected SwitchBot device, with plain-English command dropdowns and typed parameter fields, so controlling a device never requires looking up a command string or a parameter format.

**Architecture:** A build-time generator parses the 84 per-device markdown files in `OpenWonderLabs/SwitchBotAPI` into a committed `command_index.py`, merged at import time with a hand-written `command_overlay.py`. At runtime, `service_generator.py` crosses the cached device list with that index to emit `services.yaml` via `yaml.safe_dump` and register one handler per generated action. Infrared custom button names, which the API cannot expose, are collected through the options flow and auto-remembered on successful sends.

**Tech Stack:** Python 3.11+, Home Assistant custom integration (`voluptuous` schemas, config/options flows), PyYAML (provided by HA core), pytest (dev only, no HA required).

**Spec:** `docs/superpowers/specs/2026-09-22-switchbot-command-ui-design.md`

## Global Constraints

- Home Assistant floor is **2024.1.0** (`hacs.json`). Do not use APIs newer than that.
- **No new runtime dependencies.** `manifest.json` `requirements` stays `[]`. PyYAML is available because HA core depends on it.
- **Tests must pass with `homeassistant` NOT installed.** Every module under test must be free of `homeassistant` imports. Modules that need HA (`services.py`, `config_flow.py`, `__init__.py`, `button.py`, `sensor.py`, `api.py`) are verified by the maintainer in a live HA, not by pytest.
- **Custom IR button names are stored and compared verbatim** — case-sensitive, never slugged, never normalized.
- **Generated YAML is produced with `yaml.safe_dump`.** Never f-string interpolation.
- **No file I/O on the event loop.** All writes go through `hass.async_add_executor_job`.
- **`switchbot_api.send_command` keeps its current name, fields and behaviour.** No migration, no deprecation.
- `hacs.json` sets `content_in_root: true`, so `tools/`, `tests/` and `docs/` ship to users. Keep them small; never import them from integration code.
- Target release version: **4.0.0**.
- Use `from __future__ import annotations` in every new module, matching the existing files.
- Field names on dataclasses must not shadow builtins: use `minimum`/`maximum`, not `min`/`max`.

---

## File Structure

**New — pure Python, no Home Assistant imports, fully unit tested:**

| File | Responsibility |
| --- | --- |
| `command_types.py` | `ParamField`, `CommandDef`, `ParameterError`, `resolve_values()`, `encode_parameter()`. Leaf module — imports only stdlib. |
| `command_index.py` | Generated. `COMMAND_INDEX` (physical) and `IR_COMMAND_INDEX` (infrared). Committed, never hand-edited. |
| `command_overlay.py` | Hand-written. `COMMAND_OVERLAY`, `DEVICE_TYPE_ALIASES`, `PARAMETER_OPTION_LABELS`. Survives regeneration. |
| `service_generator.py` | `slugify()`, `build_services()`, `render_services_yaml()`. Pure functions; the HA-facing registration wrapper lives in `services.py`. |

**New — build-time only, never imported by Home Assistant:**

| File | Responsibility |
| --- | --- |
| `tools/doc_parser.py` | Markdown `## Control Commands` tables to `CommandRow` records. No network. |
| `tools/schema_derive.py` | `CommandRow` to `(fields, encoding, literal_parameter)`. No network. |
| `tools/generate_command_index.py` | CLI: fetch upstream docs, parse, derive, emit `command_index.py`, print a report. |

**Rewritten:**

| File | Change |
| --- | --- |
| `device_commands.py` | Becomes the merge + lookup layer over `command_index` and `command_overlay`. Keeps `get_commands_for_device_type()` and `get_parameter_label()` signatures. Gains `find_command()` and `resolve_command_type()`. |

**Modified:**

| File | Change |
| --- | --- |
| `services.py` | Extract `_async_send()`; executor-based YAML write; call the generator; register/unregister generated services; IR command-type fix; auto-remember. |
| `config_flow.py` | Options flow becomes a menu; adds IR button steps; merging save. |
| `__init__.py` | Regenerate services unconditionally on setup. |
| `README.md`, `manifest.json` | Docs and version 4.0.0. |

**Tests:** `tests/conftest.py`, `tests/fixtures/*.md`, and one test module per unit above.

Why `command_types.py` exists separately: `command_index.py` and `command_overlay.py` both need the dataclasses, and `device_commands.py` imports both. Putting the dataclasses in `device_commands.py` would make that a circular import.

---

## Task 1: Probe whether new actions need a Home Assistant restart

The spec flags one unknown: whether HA re-reads `services.yaml` and shows newly registered actions without a restart. Everything downstream assumes it does. Settle it before building on it. **This task keeps no code.**

**Files:**
- Modify (temporarily, then revert): `services.py:123-168`

- [ ] **Step 1: Add a throwaway probe service to the generated YAML**

In `_write_services_yaml()`, append a hardcoded extra service to the end of the `content` string, immediately before the closing `"""`:

```python
    content += """
zzz_probe_service:
  name: "SwitchBot: PROBE - delete me"
  description: "Temporary probe. If you can see this, no restart was needed."
  fields:
    probe_field:
      name: "Probe field"
      required: false
      selector:
        select:
          options:
            - {label: "Probe option A", value: a}
            - {label: "Probe option B", value: b}
"""
```

- [ ] **Step 2: Register it alongside the real services**

In `async_setup_services()`, after the existing `send_command` registration block, add:

```python
    async def _probe(call):
        return None

    if not hass.services.has_service(DOMAIN, "zzz_probe_service"):
        hass.services.async_register(DOMAIN, "zzz_probe_service", _probe)
```

- [ ] **Step 3: Test it in a running Home Assistant WITHOUT restarting**

Copy the modified `services.py` into `config/custom_components/switchbot_api/`, then in the HA UI:
1. Go to **Developer Tools -> Actions**, reload the browser page only.
2. Search for `PROBE`.

Record which happened:
- **Action appears with its name, description and the two-option dropdown** -> the assumption holds. Proceed with the plan unchanged.
- **Action appears but with raw keys and no description** -> `services.yaml` was not re-read. Proceed, but add to Task 10 a `homeassistant.reload_custom_templates`-style hint: after regeneration, raise a persistent notification telling the user to reload the integration.
- **Action does not appear at all** -> registration needs a reload. Proceed, and in Task 10 call `hass.config_entries.async_schedule_reload(entry.entry_id)` after regeneration instead of registering in place.

- [ ] **Step 4: Revert the probe completely**

```bash
git checkout -- services.py
git status --short
```

Expected: no output. The probe leaves no trace.

- [ ] **Step 5: Record the finding in the spec**

Append the observed outcome to the "Risks and unknowns" section of `docs/superpowers/specs/2026-09-22-switchbot-command-ui-design.md`, replacing the paragraph that says it is unconfirmed.

```bash
git add docs/superpowers/specs/2026-09-22-switchbot-command-ui-design.md
git commit -m "docs: record HA service-reload probe result"
```

---

## Task 2: Test harness that works without Home Assistant

**Files:**
- Create: `.venv/` (gitignored), `pytest.ini`, `tests/conftest.py`, `tests/fixtures/*.md`, `tests/test_harness.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `load_integration_module(name)` — imports a module from the repo root by filename, resolving its relative imports, without executing `__init__.py`. Every later test module uses it.

Why this is needed: the repo root *is* the integration package, and `__init__.py` imports `homeassistant`. A plain `import device_commands` breaks on the relative imports inside it (`from .command_types import ...`); `import switchbot_api.device_commands` executes `__init__.py` and fails. The loader installs a synthetic parent package whose `__path__` is the repo root, so relative imports resolve and `__init__.py` is never touched.

- [ ] **Step 1: Create the virtualenv and install dev dependencies**

```bash
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet pytest pyyaml
.venv/bin/pytest --version
```

Expected: a pytest version string.

- [ ] **Step 2: Gitignore the venv**

```bash
printf '.venv/\n.pytest_cache/\n' >> .gitignore
```

- [ ] **Step 3: Add pytest configuration**

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 4: Write the module loader**

Create `tests/conftest.py`:

```python
"""Load integration modules for tests without importing Home Assistant.

The repository root is the integration package, and its __init__.py imports
homeassistant. A synthetic parent package lets relative imports inside the
modules under test resolve without __init__.py ever running.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYNTHETIC_PKG = "switchbot_api_under_test"


def _ensure_package() -> None:
    if SYNTHETIC_PKG in sys.modules:
        return
    pkg = types.ModuleType(SYNTHETIC_PKG)
    pkg.__path__ = [str(ROOT)]
    sys.modules[SYNTHETIC_PKG] = pkg


def load_integration_module(name: str):
    """Import <repo root>/<name>.py with relative imports working."""
    _ensure_package()
    full_name = f"{SYNTHETIC_PKG}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    path = ROOT / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"no module at {path}")
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def load_tool_module(name: str):
    """Import <repo root>/tools/<name>.py as a standalone module."""
    path = ROOT / "tools" / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"no module at {path}")
    full_name = f"switchbot_api_tools_{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 5: Write a test proving the loader works on the module that exists today**

Create `tests/test_harness.py`:

```python
from conftest import load_integration_module


def test_loader_imports_existing_device_commands():
    mod = load_integration_module("device_commands")
    commands = mod.get_commands_for_device_type("Bot")
    assert [c.command for c in commands] == ["turnOn", "turnOff", "press"]


def test_loader_does_not_import_homeassistant():
    import sys

    load_integration_module("device_commands")
    assert "homeassistant" not in sys.modules
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/pytest tests/test_harness.py -v`
Expected: 2 passed. If `ModuleNotFoundError: conftest`, add `ROOT`-relative import support by running pytest from the repo root (pytest puts `tests/` on `sys.path` via rootdir insertion).

- [ ] **Step 7: Download the upstream markdown fixtures**

```bash
mkdir -p tests/fixtures
BASE=https://raw.githubusercontent.com/OpenWonderLabs/SwitchBotAPI/main/devices
curl -sL $BASE/curtains-blinds/curtain-3.md          -o tests/fixtures/curtain-3.md
curl -sL $BASE/climate-control/evaporative-humidifier.md -o tests/fixtures/evaporative-humidifier.md
curl -sL $BASE/others/virtual-infrared-remote-devices.md -o tests/fixtures/virtual-infrared-remote-devices.md
curl -sL $BASE/plugs-switches/plug-mini-jp.md        -o tests/fixtures/plug-mini-jp.md
curl -sL $BASE/others/bot.md                         -o tests/fixtures/bot.md
wc -l tests/fixtures/*.md
```

Expected: five files, each non-empty. These are the real upstream tables, so parser tests need no network.

- [ ] **Step 8: Commit**

```bash
git add .gitignore pytest.ini tests/
git commit -m "test: add HA-free test harness and upstream markdown fixtures"
```

---

## Task 3: `command_types.py` — parameter schema and encoding

**Files:**
- Create: `command_types.py`
- Test: `tests/test_parameter_encoding.py`

**Interfaces:**
- Produces:
  - `ParamField(key, label, kind="text", required=True, default=None, minimum=None, maximum=None, unit=None, options=(), value_type="auto", help="")` — frozen dataclass. `kind` is one of `"number" | "select" | "boolean" | "text"`. `options` is a tuple of `(value, label)` pairs. `value_type` is one of `"auto" | "str" | "int" | "bool"`.
  - `CommandDef(command, label="", description="", command_type="command", parameter="default", fields=(), encoding="none")` — frozen dataclass. `encoding` is one of `"none" | "csv" | "json" | "scalar"`.
  - `ParameterError(ValueError)`
  - `resolve_values(command_def, supplied) -> dict[str, str]`
  - `encode_parameter(command_def, supplied) -> str | dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_parameter_encoding.py`:

```python
import pytest

from conftest import load_integration_module

ct = load_integration_module("command_types")


def _set_position():
    """Curtain 3 setPosition: wire order is index,mode,position."""
    return ct.CommandDef(
        command="setPosition",
        label="Move to position",
        encoding="csv",
        parameter="",
        fields=(
            ct.ParamField(key="index", label="Curtain", kind="number", default="0"),
            ct.ParamField(
                key="mode",
                label="Mode",
                kind="select",
                default="ff",
                options=(("ff", "Default"), ("0", "Performance"), ("1", "Silent")),
            ),
            ct.ParamField(key="position", label="Position", kind="number",
                          minimum=0, maximum=100, unit="%"),
        ),
    )


def _set_all():
    """Air Conditioner setAll: temperature,mode,fan speed,power state."""
    return ct.CommandDef(
        command="setAll",
        encoding="csv",
        parameter="",
        fields=(
            ct.ParamField(key="temperature", label="Temperature", kind="number"),
            ct.ParamField(key="mode", label="Mode", kind="select",
                          options=(("1", "Auto"), ("2", "Cool"))),
            ct.ParamField(key="fan_speed", label="Fan speed", kind="select",
                          options=(("3", "Medium"),)),
            ct.ParamField(key="power_state", label="Power", kind="select",
                          options=(("on", "On"), ("off", "Off"))),
        ),
    )


def _set_mode_json():
    """Humidifier2 setMode: {"mode": int, "targetHumidify": int}."""
    return ct.CommandDef(
        command="setMode",
        encoding="json",
        parameter="",
        fields=(
            ct.ParamField(key="mode", label="Mode", kind="select",
                          options=(("7", "Auto"),)),
            ct.ParamField(key="targetHumidify", label="Target humidity",
                          kind="number", minimum=0, maximum=100),
        ),
    )


def test_no_fields_returns_literal_parameter():
    cmd = ct.CommandDef(command="turnOn", parameter="default", encoding="none")
    assert ct.encode_parameter(cmd, {}) == "default"


def test_csv_uses_wire_order_and_fills_defaults():
    # Only position supplied; index and mode come from defaults.
    assert ct.encode_parameter(_set_position(), {"position": 80}) == "0,ff,80"


def test_csv_respects_supplied_values_over_defaults():
    assert ct.encode_parameter(
        _set_position(), {"position": 50, "mode": "1", "index": "2"}
    ) == "2,1,50"


def test_csv_air_conditioner():
    assert ct.encode_parameter(
        _set_all(),
        {"temperature": 26, "mode": "2", "fan_speed": "3", "power_state": "on"},
    ) == "26,2,3,on"


def test_json_coerces_digit_strings_to_int():
    assert ct.encode_parameter(
        _set_mode_json(), {"mode": "7", "targetHumidify": "50"}
    ) == {"mode": 7, "targetHumidify": 50}


def test_json_keeps_non_numeric_as_string():
    cmd = ct.CommandDef(
        command="setThing",
        encoding="json",
        fields=(ct.ParamField(key="name", label="Name"),),
    )
    assert ct.encode_parameter(cmd, {"name": "kitchen"}) == {"name": "kitchen"}


def test_value_type_str_forces_string_in_json():
    cmd = ct.CommandDef(
        command="setThing",
        encoding="json",
        fields=(ct.ParamField(key="code", label="Code", value_type="str"),),
    )
    assert ct.encode_parameter(cmd, {"code": "01"}) == {"code": "01"}


def test_scalar_passes_single_value_as_string():
    cmd = ct.CommandDef(
        command="SetChannel",
        encoding="scalar",
        fields=(ct.ParamField(key="channel", label="Channel", kind="number"),),
    )
    assert ct.encode_parameter(cmd, {"channel": 15}) == "15"


def test_missing_value_with_no_default_raises():
    with pytest.raises(ct.ParameterError) as exc:
        ct.encode_parameter(_set_position(), {})
    assert "Position" in str(exc.value)


def test_empty_string_is_treated_as_missing():
    with pytest.raises(ct.ParameterError):
        ct.encode_parameter(_set_position(), {"position": ""})


def test_boolean_scalar_encodes_lowercase():
    cmd = ct.CommandDef(
        command="setChildLock",
        encoding="scalar",
        fields=(ct.ParamField(key="enabled", label="Enabled", kind="boolean",
                              value_type="bool"),),
    )
    assert ct.encode_parameter(cmd, {"enabled": True}) == "true"
    assert ct.encode_parameter(cmd, {"enabled": False}) == "false"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_parameter_encoding.py -v`
Expected: collection error — `FileNotFoundError: no module at .../command_types.py`.

- [ ] **Step 3: Write the implementation**

Create `command_types.py`:

```python
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
        return int(raw)
    if fld.value_type == "bool":
        return _as_bool_text(raw) == "true"
    text = str(raw)
    if text.lstrip("-").isdigit():
        return int(text)
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_parameter_encoding.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add command_types.py tests/test_parameter_encoding.py
git commit -m "feat: add ParamField/CommandDef schema and parameter encoding"
```

---

## Task 4: `tools/doc_parser.py` — upstream markdown to command rows

**Files:**
- Create: `tools/doc_parser.py`
- Test: `tests/test_doc_parser.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (deliberately independent of `command_types`).
- Produces:
  - `CommandRow(device_type, command_type, command, parameter_spec, description)` — frozen dataclass of raw strings.
  - `DeviceTypeConflict(Exception)`
  - `parse_control_commands(markdown) -> list[CommandRow]`
  - `extract_declared_device_type(markdown) -> str | None`
  - `expand_device_types(row) -> list[CommandRow]`
  - `check_device_type_agreement(declared, table_types) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_doc_parser.py`:

```python
import pathlib

import pytest

from conftest import load_tool_module

dp = load_tool_module("doc_parser")
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_curtain_3_commands():
    rows = dp.parse_control_commands(fixture("curtain-3.md"))
    assert [r.command for r in rows] == ["setPosition", "turnOff", "turnOn", "pause"]
    assert all(r.device_type == "Curtain 3" for r in rows)
    assert all(r.command_type == "command" for r in rows)


def test_captures_parameter_spec_and_description():
    rows = dp.parse_control_commands(fixture("curtain-3.md"))
    set_position = next(r for r in rows if r.command == "setPosition")
    assert "index0,mode0,position0" in set_position.parameter_spec
    assert "0,ff,80" in set_position.parameter_spec
    assert "Performance Mode" in set_position.description


def test_strips_html_line_breaks():
    rows = dp.parse_control_commands(fixture("curtain-3.md"))
    set_position = next(r for r in rows if r.command == "setPosition")
    assert "<br />" not in set_position.parameter_spec
    assert "<br />" not in set_position.description


def test_default_parameter_is_preserved():
    rows = dp.parse_control_commands(fixture("curtain-3.md"))
    turn_on = next(r for r in rows if r.command == "turnOn")
    assert turn_on.parameter_spec == "default"


def test_parses_json_object_parameter():
    rows = dp.parse_control_commands(fixture("evaporative-humidifier.md"))
    set_mode = next(r for r in rows if r.command == "setMode")
    assert set_mode.parameter_spec.startswith("{")
    assert "targetHumidify" in set_mode.parameter_spec


def test_strips_backticks_from_boolean_spec():
    rows = dp.parse_control_commands(fixture("evaporative-humidifier.md"))
    child_lock = next(r for r in rows if r.command == "setChildLock")
    assert child_lock.parameter_spec == "true or false"


def test_carries_device_type_forward_across_blank_cells():
    """Upstream's IR table leaves deviceType blank to mean 'same as above'."""
    rows = dp.parse_control_commands(fixture("virtual-infrared-remote-devices.md"))
    volume_add = next(r for r in rows if r.command == "volumeAdd")
    assert volume_add.device_type == "TV, IPTV/Streamer, Set Top Box"


def test_skips_fully_empty_separator_rows():
    rows = dp.parse_control_commands(fixture("virtual-infrared-remote-devices.md"))
    assert all(r.command for r in rows)


def test_strips_backticks_from_command_type():
    rows = dp.parse_control_commands(fixture("virtual-infrared-remote-devices.md"))
    custom = next(r for r in rows if "user-defined" in r.command)
    assert custom.command_type == "customize"


def test_expand_device_types_splits_comma_lists():
    row = dp.CommandRow(
        device_type="TV, IPTV/Streamer, Set Top Box",
        command_type="command",
        command="volumeAdd",
        parameter_spec="default",
        description="volume up",
    )
    assert [r.device_type for r in dp.expand_device_types(row)] == [
        "TV",
        "IPTV/Streamer",
        "Set Top Box",
    ]


def test_expand_device_types_handles_all_except_others():
    row = dp.CommandRow(
        device_type="All home appliance types except Others",
        command_type="command",
        command="turnOn",
        parameter_spec="default",
        description="every home appliance can be turned on by default",
    )
    expanded = dp.expand_device_types(row)
    assert [r.device_type for r in expanded] == [dp.ALL_IR_EXCEPT_OTHERS]


def test_extracts_declared_device_type():
    assert dp.extract_declared_device_type(fixture("curtain-3.md")) == "Curtain3"


def test_device_type_agreement_accepts_known_alias():
    dp.check_device_type_agreement("Curtain3", {"Curtain 3"})


def test_device_type_agreement_raises_on_unreconciled_mismatch():
    with pytest.raises(dp.DeviceTypeConflict) as exc:
        dp.check_device_type_agreement("WidgetPro", {"Widget Deluxe"})
    assert "WidgetPro" in str(exc.value)
    assert "Widget Deluxe" in str(exc.value)


def test_no_control_commands_section_returns_empty():
    assert dp.parse_control_commands("# Meter\n\nNo commands here.\n") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_doc_parser.py -v`
Expected: collection error — `FileNotFoundError: no module at .../tools/doc_parser.py`.

- [ ] **Step 3: Write the implementation**

Create `tools/doc_parser.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_doc_parser.py -v`
Expected: 15 passed. If `test_carries_device_type_forward_across_blank_cells` fails, print the parsed rows and check whether upstream changed the IR table's layout.

- [ ] **Step 5: Commit**

```bash
git add tools/doc_parser.py tests/test_doc_parser.py
git commit -m "feat: parse upstream SwitchBot Control Commands tables"
```

---

## Task 5: `tools/schema_derive.py` — parameter specs to typed fields

**Files:**
- Create: `tools/schema_derive.py`
- Test: `tests/test_schema_derivation.py`

**Interfaces:**
- Consumes: `CommandRow` from `tools/doc_parser.py`; `ParamField`, `CommandDef` from `command_types.py`.
- Produces: `derive_command(row) -> CommandDef`, `humanize_command(name) -> str`, `humanize_key(key) -> str`, `parse_paren_enum(text, key) -> tuple[tuple[str, str], ...]`, `parse_backtick_enum(text, key) -> tuple[tuple[str, str], ...]`, `parse_range(text, key) -> tuple[int, int] | None`.

Note on slash groups: upstream writes `modes include 0/1 (auto), 2 (cool)`. A dropdown cannot show two options labelled "Auto", so a slash group collapses to its **last** value — `1` — which is also the value upstream uses in its own `26,1,3,on` example.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_schema_derivation.py`:

```python
from conftest import load_integration_module, load_tool_module

sd = load_tool_module("schema_derive")
dp = load_tool_module("doc_parser")
ct = load_integration_module("command_types")


def row(command, parameter_spec, description, device_type="Curtain 3",
        command_type="command"):
    return dp.CommandRow(
        device_type=device_type,
        command_type=command_type,
        command=command,
        parameter_spec=parameter_spec,
        description=description,
    )


def test_default_parameter_yields_no_fields():
    cmd = sd.derive_command(row("turnOn", "default", "set to ON state"))
    assert cmd.fields == ()
    assert cmd.encoding == "none"
    assert cmd.parameter == "default"
    assert cmd.command_type == "command"


def test_command_label_is_humanized():
    cmd = sd.derive_command(row("setPosition", "default", ""))
    assert cmd.label == "Set position"


def test_positional_spec_becomes_csv_fields_in_wire_order():
    cmd = sd.derive_command(
        row(
            "setPosition",
            "index0,mode0,position0 e.g. 0,ff,80",
            "mode: 0 (Performance Mode), 1 (Silent Mode), ff (default mode) "
            "position: 0~100 (0 means open, 100 means closed)",
        )
    )
    assert cmd.encoding == "csv"
    assert [f.key for f in cmd.fields] == ["index", "mode", "position"]


def test_positional_fields_pick_up_enum_options():
    cmd = sd.derive_command(
        row(
            "setPosition",
            "index0,mode0,position0 e.g. 0,ff,80",
            "mode: 0 (Performance Mode), 1 (Silent Mode), ff (default mode) "
            "position: 0~100 (0 means open, 100 means closed)",
        )
    )
    mode = next(f for f in cmd.fields if f.key == "mode")
    assert mode.kind == "select"
    assert dict(mode.options) == {
        "0": "Performance Mode",
        "1": "Silent Mode",
        "ff": "Default mode",
    }


def test_positional_fields_pick_up_ranges():
    cmd = sd.derive_command(
        row(
            "setPosition",
            "index0,mode0,position0 e.g. 0,ff,80",
            "mode: 0 (Performance Mode), 1 (Silent Mode), ff (default mode) "
            "position: 0~100 (0 means open, 100 means closed)",
        )
    )
    position = next(f for f in cmd.fields if f.key == "position")
    assert position.kind == "number"
    assert (position.minimum, position.maximum) == (0, 100)


def test_defaults_come_from_the_example():
    cmd = sd.derive_command(
        row("setPosition", "index0,mode0,position0 e.g. 0,ff,80", "")
    )
    assert [f.default for f in cmd.fields] == ["0", "ff", "80"]


def test_air_conditioner_set_all():
    cmd = sd.derive_command(
        row(
            "setAll",
            "{temperature},{mode},{fan speed},{power state} e.g. 26,1,3,on",
            "the unit of temperature is in celsius; modes include 0/1 (auto), "
            "2 (cool), 3 (dry), 4 (fan), 5 (heat); fan speed includes 1 (auto), "
            "2 (low), 3 (medium), 4 (high); power state includes on and off",
            device_type="Air Conditioner",
        )
    )
    assert cmd.encoding == "csv"
    assert [f.key for f in cmd.fields] == [
        "temperature", "mode", "fan_speed", "power_state"
    ]
    mode = next(f for f in cmd.fields if f.key == "mode")
    # A slash group collapses to its last value, so "0/1 (auto)" yields "1".
    assert dict(mode.options) == {
        "1": "Auto", "2": "Cool", "3": "Dry", "4": "Fan", "5": "Heat"
    }


def test_json_object_spec_becomes_json_fields():
    cmd = sd.derive_command(
        row(
            "setMode",
            '{"mode": mode_int, "targetHumidify": humidity_int}',
            "set the mode. mode_int, 1, level 4; 2, level 3; 3, level 2; "
            "4, level 1; 5, humidity mode; 6, sleep mode; 7, auto mode; "
            "8, drying mode; targetHumidify, the target humidity level in "
            "percentage, 0~100.",
            device_type="Humidifier2",
        )
    )
    assert cmd.encoding == "json"
    assert [f.key for f in cmd.fields] == ["mode", "targetHumidify"]
    target = next(f for f in cmd.fields if f.key == "targetHumidify")
    assert (target.minimum, target.maximum) == (0, 100)


def test_boolean_spec_becomes_boolean_field():
    cmd = sd.derive_command(
        row("setChildLock", "true or false",
            "enable or disable child lock. true, enable; false, disable",
            device_type="Humidifier2")
    )
    assert cmd.encoding == "scalar"
    assert cmd.fields[0].kind == "boolean"
    assert cmd.fields[0].value_type == "bool"


def test_numeric_scalar_spec_becomes_number_field():
    cmd = sd.derive_command(
        row("SetChannel", "{channel number}, e.g. 15",
            "set the TV channel to switch to", device_type="TV")
    )
    assert cmd.encoding == "scalar"
    assert cmd.fields[0].kind == "number"
    assert cmd.fields[0].key == "channel_number"


def test_unparseable_spec_falls_back_to_text_with_help():
    cmd = sd.derive_command(
        row("setSomething", "a free-form incantation",
            "do the needful in an undocumented way")
    )
    assert cmd.encoding == "scalar"
    assert cmd.fields[0].kind == "text"
    assert cmd.fields[0].help == "do the needful in an undocumented way"


def test_customize_command_type_is_preserved():
    cmd = sd.derive_command(
        row("{user-defined button name}", "default",
            "all user-defined buttons must be configured with "
            "commandType=customize",
            device_type="Others", command_type="customize")
    )
    assert cmd.command_type == "customize"


def test_humanize_key_splits_camel_case():
    assert sd.humanize_key("targetHumidify") == "Target humidify"
    assert sd.humanize_key("fan speed") == "Fan speed"


def test_humanize_command_splits_camel_case():
    assert sd.humanize_command("brightnessUp") == "Brightness up"
    assert sd.humanize_command("turnOn") == "Turn on"
    assert sd.humanize_command("SetChannel") == "Set channel"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_schema_derivation.py -v`
Expected: collection error — no `tools/schema_derive.py`.

- [ ] **Step 3: Write the implementation**

Create `tools/schema_derive.py`:

```python
"""Derive typed parameter fields from upstream documentation prose.

Build-time only. Anything this cannot parse confidently degrades to a single
text field carrying the upstream description, and is reported by the generator
as a candidate for command_overlay.py.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_command_types():
    """Import command_types.py from the repo root without the HA package."""
    name = "switchbot_api_command_types"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _ROOT / "command_types.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ct = _load_command_types()
CommandDef = _ct.CommandDef
ParamField = _ct.ParamField

_EXAMPLE_RE = re.compile(r"e\.g\.\s*([^\s;]+)", re.IGNORECASE)
_RANGE_RE = re.compile(r"(\d+)\s*[~-]\s*(\d+)")
_JSON_KEY_RE = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:')
_PAREN_ENUM_RE = re.compile(r"([A-Za-z0-9/]+)\s*\(([^)]+)\)")
_BACKTICK_ENUM_RE = re.compile(r"(?:^|;)\s*([A-Za-z0-9]+)\s*,\s*([^;,]+)")


def humanize_command(name: str) -> str:
    """turnOn -> 'Turn on'; brightnessUp -> 'Brightness up'."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    spaced = spaced.replace("_", " ").strip()
    if not spaced:
        return name
    words = spaced.split()
    return " ".join([words[0].capitalize()] + [w.lower() for w in words[1:]])


def humanize_key(key: str) -> str:
    """targetHumidify -> 'Target humidify'; 'fan speed' -> 'Fan speed'."""
    return humanize_command(key)


def _normalize_key(raw: str) -> str:
    """'{fan speed}' -> 'fan_speed'; 'index0' -> 'index'."""
    text = raw.strip().strip("{}").strip()
    text = re.sub(r"\d+$", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text or "value"


def parse_range(text: str, key: str) -> tuple[int, int] | None:
    """Find a numeric range documented for `key`, e.g. 'position: 0~100'."""
    window = _describe_window(text, key)
    match = _RANGE_RE.search(window)
    if not match:
        return None
    low, high = int(match.group(1)), int(match.group(2))
    return (low, high) if low < high else None


def _describe_window(text: str, key: str) -> str:
    """Slice the description around the clause that documents `key`."""
    pretty = key.replace("_", " ")
    for needle in (key, pretty, pretty.split()[0]):
        idx = text.lower().find(needle.lower())
        if idx != -1:
            return text[idx : idx + 220]
    return text


def parse_paren_enum(text: str, key: str) -> tuple[tuple[str, str], ...]:
    """'mode: 0 (Performance Mode), 1 (Silent Mode)' -> (('0','Performance Mode'),...)."""
    window = _describe_window(text, key)
    options: list[tuple[str, str]] = []
    for value, label in _PAREN_ENUM_RE.findall(window):
        # A slash group collapses to its last value: "0/1 (auto)" -> "1".
        candidate = value.split("/")[-1].strip()
        if not candidate:
            continue
        pretty = label.strip().rstrip(".")
        pretty = re.sub(r"\s+", " ", pretty)
        pretty = pretty[0].upper() + pretty[1:] if pretty else pretty
        if candidate not in dict(options):
            options.append((candidate, pretty))
    return tuple(options)


def parse_backtick_enum(text: str, key: str) -> tuple[tuple[str, str], ...]:
    """'mode_int, 1, level 4; 2, level 3' -> (('1','Level 4'), ('2','Level 3'))."""
    window = _describe_window(text, key)
    options: list[tuple[str, str]] = []
    for value, label in _BACKTICK_ENUM_RE.findall(window):
        if not value.isdigit():
            continue
        pretty = label.strip().rstrip(".")
        pretty = pretty[0].upper() + pretty[1:] if pretty else pretty
        if value not in dict(options):
            options.append((value, pretty))
    return tuple(options)


def _build_field(key: str, description: str, default: str | None) -> ParamField:
    options = parse_paren_enum(description, key) or parse_backtick_enum(
        description, key
    )
    bounds = parse_range(description, key)

    if options and len(options) > 1:
        return ParamField(
            key=key,
            label=humanize_key(key),
            kind="select",
            default=default,
            options=options,
        )
    if bounds:
        return ParamField(
            key=key,
            label=humanize_key(key),
            kind="number",
            default=default,
            minimum=bounds[0],
            maximum=bounds[1],
        )
    if default is not None and default.lstrip("-").isdigit():
        return ParamField(
            key=key, label=humanize_key(key), kind="number", default=default
        )
    return ParamField(key=key, label=humanize_key(key), default=default)


def derive_command(row) -> CommandDef:
    """Turn one upstream table row into a CommandDef."""
    spec = row.parameter_spec.strip()
    description = row.description.strip()
    label = humanize_command(row.command)
    base = {
        "command": row.command,
        "label": label,
        "description": description,
        "command_type": row.command_type or "command",
    }

    if spec.lower() in ("default", "", "-"):
        return CommandDef(**base, parameter="default", encoding="none")

    if spec.startswith("{") and '"' in spec:
        keys = _JSON_KEY_RE.findall(spec)
        if keys:
            fields = tuple(_build_field(k, description, None) for k in keys)
            return CommandDef(**base, parameter="", fields=fields, encoding="json")

    example = _EXAMPLE_RE.search(spec)
    head = spec.split("e.g.")[0].strip().rstrip(",").strip()
    if "," in head:
        parts = [p for p in head.split(",") if p.strip()]
        defaults: list[str | None] = [None] * len(parts)
        if example:
            sample = example.group(1).strip().strip("`").split(",")
            if len(sample) == len(parts):
                defaults = [s.strip() for s in sample]
        fields = tuple(
            _build_field(_normalize_key(part), description, defaults[i])
            for i, part in enumerate(parts)
        )
        return CommandDef(**base, parameter="", fields=fields, encoding="csv")

    if re.fullmatch(r"(true or false|true/false)", spec, re.IGNORECASE):
        return CommandDef(
            **base,
            parameter="",
            encoding="scalar",
            fields=(
                ParamField(
                    key="enabled",
                    label="Enabled",
                    kind="boolean",
                    value_type="bool",
                    help=description,
                ),
            ),
        )

    key = _normalize_key(head or spec)
    bounds = parse_range(description, key) or parse_range(spec, key)
    is_numeric = bool(bounds) or "number" in head.lower() or (
        example and example.group(1).strip().isdigit()
    )
    field = ParamField(
        key=key,
        label=humanize_key(key),
        kind="number" if is_numeric else "text",
        minimum=bounds[0] if bounds else None,
        maximum=bounds[1] if bounds else None,
        help=description,
    )
    return CommandDef(**base, parameter="", fields=(field,), encoding="scalar")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_schema_derivation.py -v`
Expected: 15 passed. These regexes are the most fragile code in the project — if a test fails, print the derived `CommandDef` and adjust the regex rather than loosening the assertion.

- [ ] **Step 5: Commit**

```bash
git add tools/schema_derive.py tests/test_schema_derivation.py
git commit -m "feat: derive typed parameter fields from upstream docs"
```

---

## Task 6: `tools/generate_command_index.py` and the generated index

**Files:**
- Create: `tools/generate_command_index.py`, `command_index.py` (generated output, committed)
- Test: `tests/test_index_emission.py`

**Interfaces:**
- Consumes: `doc_parser`, `schema_derive`, `command_types`.
- Produces: `render_index_module(physical, infrared) -> str`; a committed `command_index.py` exporting `COMMAND_INDEX: dict[str, list[CommandDef]]` and `IR_COMMAND_INDEX: dict[str, list[CommandDef]]`.

Emission relies on dataclass `repr` being valid Python given `CommandDef` and `ParamField` are imported — no hand-rolled serializer.

- [ ] **Step 1: Write the failing test for emission**

Create `tests/test_index_emission.py`:

```python
from conftest import load_integration_module, load_tool_module

gen = load_tool_module("generate_command_index")
ct = load_integration_module("command_types")


def test_rendered_module_is_valid_python_and_round_trips():
    physical = {
        "Bot": [
            ct.CommandDef(command="turnOn", label="Turn on", encoding="none"),
            ct.CommandDef(
                command="setPosition",
                label="Move to position",
                encoding="csv",
                parameter="",
                fields=(
                    ct.ParamField(key="position", label="Position", kind="number",
                                  minimum=0, maximum=100),
                ),
            ),
        ]
    }
    infrared = {
        "TV": [ct.CommandDef(command="volumeAdd", label="Volume up")],
    }

    source = gen.render_index_module(physical, infrared)

    namespace = {"CommandDef": ct.CommandDef, "ParamField": ct.ParamField}
    exec(compile(source.replace("from .command_types import", "# from"),
                 "<generated>", "exec"), namespace)

    assert namespace["COMMAND_INDEX"]["Bot"][0].command == "turnOn"
    assert namespace["COMMAND_INDEX"]["Bot"][1].fields[0].maximum == 100
    assert namespace["IR_COMMAND_INDEX"]["TV"][0].label == "Volume up"


def test_rendered_module_declares_its_relative_import():
    source = gen.render_index_module({}, {})
    assert "from .command_types import CommandDef, ParamField" in source


def test_rendered_module_warns_against_hand_editing():
    source = gen.render_index_module({}, {})
    assert "generated" in source.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_index_emission.py -v`
Expected: collection error — no `tools/generate_command_index.py`.

- [ ] **Step 3: Write the generator**

Create `tools/generate_command_index.py`:

```python
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
```

- [ ] **Step 4: Run the emission test to verify it passes**

Run: `.venv/bin/pytest tests/test_index_emission.py -v`
Expected: 3 passed.

- [ ] **Step 5: Generate the real index**

```bash
.venv/bin/python tools/generate_command_index.py
```

Expected: a report ending in `wrote command_index.py`. If it raises `DeviceTypeConflict`, add the named spelling pair to `RECONCILED_TYPES` in `tools/doc_parser.py` and rerun — that error is the parser refusing to silently drop a device type.

- [ ] **Step 6: Sanity-check the generated file**

```bash
.venv/bin/python -c "
import importlib.util, sys, types, pathlib
root = pathlib.Path('.').resolve()
pkg = types.ModuleType('p'); pkg.__path__=[str(root)]; sys.modules['p']=pkg
for name in ('command_types','command_index'):
    spec = importlib.util.spec_from_file_location(f'p.{name}', root/f'{name}.py')
    m = importlib.util.module_from_spec(spec); sys.modules[f'p.{name}']=m
    spec.loader.exec_module(m)
ci = sys.modules['p.command_index']
print('physical types:', len(ci.COMMAND_INDEX))
print('ir types:', len(ci.IR_COMMAND_INDEX))
print('Curtain 3:', [c.command for c in ci.COMMAND_INDEX.get('Curtain 3', [])])
"
```

Expected: a non-trivial count for both, and `Curtain 3` listing `setPosition`, `turnOff`, `turnOn`, `pause`.

- [ ] **Step 7: Commit**

```bash
git add tools/generate_command_index.py command_index.py tests/test_index_emission.py
git commit -m "feat: generate command index from upstream SwitchBot API docs"
```

---

## Task 7: `command_overlay.py` and the rewritten `device_commands.py`

**Files:**
- Create: `command_overlay.py`
- Modify: `device_commands.py` (full rewrite; the current 1040-line hand-written map becomes overlay seed material)
- Test: `tests/test_device_commands.py`, `tests/test_ir_commands.py`

**Interfaces:**
- Consumes: `command_types.CommandDef/ParamField`, `command_index.COMMAND_INDEX/IR_COMMAND_INDEX`.
- Produces:
  - `get_commands_for_device_type(device_type, *, is_infrared=False) -> list[CommandDef]` (signature preserved from today)
  - `get_parameter_label(command, value, device_type="") -> str` (signature preserved)
  - `find_command(device_type, command, *, is_infrared=False) -> CommandDef | None`
  - `resolve_command_type(device_type, command, *, is_infrared=False, custom_buttons=()) -> str`
  - `COMMAND_OVERLAY: dict[str, dict]`, `DEVICE_TYPE_ALIASES: dict[str, str]`, `PARAMETER_OPTION_LABELS: dict[str, dict[str, str]]` in `command_overlay.py`

- [ ] **Step 1: Write the failing tests for merge and lookup**

Create `tests/test_device_commands.py`:

```python
from conftest import load_integration_module

dc = load_integration_module("device_commands")


def test_known_physical_device_has_commands():
    commands = dc.get_commands_for_device_type("Bot")
    assert "turnOn" in [c.command for c in commands]


def test_curtain_3_set_position_has_typed_fields():
    cmd = dc.find_command("Curtain 3", "setPosition")
    assert cmd is not None
    assert cmd.encoding == "csv"
    assert [f.key for f in cmd.fields] == ["index", "mode", "position"]


def test_overlay_label_wins_over_generated_label():
    cmd = dc.find_command("Curtain 3", "setPosition")
    assert cmd.label == "Move to position"


def test_overlay_label_for_turn_on_is_device_specific():
    cmd = dc.find_command("Curtain 3", "turnOn")
    assert cmd.label == "Open curtain"


def test_hub_device_types_have_no_commands():
    for device_type in ("Hub Mini", "Hub 2", "Hub 3"):
        assert dc.get_commands_for_device_type(device_type) == []


def test_sensor_device_types_have_no_commands():
    for device_type in ("Meter", "Contact Sensor", "Motion Sensor", "Remote"):
        assert dc.get_commands_for_device_type(device_type) == []


def test_alias_resolves_to_canonical_type():
    aliased = dc.get_commands_for_device_type("Evaporative Humidifier")
    canonical = dc.get_commands_for_device_type("Humidifier2")
    assert [c.command for c in aliased] == [c.command for c in canonical]
    assert aliased != []


def test_unknown_device_type_returns_empty_list():
    assert dc.get_commands_for_device_type("Nonexistent Widget 9000") == []


def test_find_command_returns_none_for_unknown_command():
    assert dc.find_command("Bot", "explode") is None


def test_get_parameter_label_still_works():
    assert dc.get_parameter_label("PowLevel", "3") == "3 - MAX"
    assert dc.get_parameter_label("PowLevel", "nope") == "nope"
```

Create `tests/test_ir_commands.py`:

```python
from conftest import load_integration_module

dc = load_integration_module("device_commands")


def test_typed_remote_standard_command_uses_command_type():
    assert dc.resolve_command_type("TV", "volumeAdd", is_infrared=True) == "command"


def test_typed_remote_custom_button_uses_customize():
    """Regression: custom buttons on typed remotes were sent as commandType=command."""
    assert (
        dc.resolve_command_type(
            "TV", "Netflix", is_infrared=True, custom_buttons=("Netflix",)
        )
        == "customize"
    )


def test_others_remote_always_uses_customize():
    assert dc.resolve_command_type("Others", "Bright", is_infrared=True) == "customize"


def test_others_remote_uses_customize_even_for_command_like_names():
    assert dc.resolve_command_type("Others", "turnOn", is_infrared=True) == "customize"


def test_custom_button_matching_is_case_sensitive():
    """Upstream documents custom button names as case-sensitive."""
    assert (
        dc.resolve_command_type(
            "TV", "netflix", is_infrared=True, custom_buttons=("Netflix",)
        )
        == "command"
    )


def test_unknown_ir_remote_type_falls_back_to_customize():
    assert (
        dc.resolve_command_type("Espresso Machine", "Brew", is_infrared=True)
        == "customize"
    )


def test_diy_prefix_is_stripped_when_resolving_standard_commands():
    assert dc.get_commands_for_device_type("DIY TV", is_infrared=True) == (
        dc.get_commands_for_device_type("TV", is_infrared=True)
    )


def test_physical_device_is_unaffected():
    assert dc.resolve_command_type("Bot", "turnOn") == "command"


def test_typed_remote_has_turn_on_from_the_all_types_row():
    commands = [c.command for c in dc.get_commands_for_device_type("TV", is_infrared=True)]
    assert "turnOn" in commands
    assert "volumeAdd" in commands


def test_others_remote_has_no_standard_commands():
    assert dc.get_commands_for_device_type("Others", is_infrared=True) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_device_commands.py tests/test_ir_commands.py -v`
Expected: failures — `find_command` and `resolve_command_type` do not exist, and `command_overlay` is missing.

- [ ] **Step 3: Write `command_overlay.py`**

Seed it from the current `device_commands.py` before rewriting. Keep `DEVICE_TYPE_ALIASES` and `PARAMETER_OPTION_LABELS` verbatim from `device_commands.py:911-1009`, and add `COMMAND_OVERLAY` entries for the labels the tests require plus every item the generator listed under "needs overlay".

```python
"""Hand-written labels and schema fixes layered over the generated index.

Survives regeneration of command_index.py. Keys are "<device type>:<command>".
Values are CommandDef field names; `fields` replaces the generated tuple
entirely, other keys patch individual attributes.
"""

from __future__ import annotations

from .command_types import ParamField

COMMAND_OVERLAY: dict[str, dict] = {
    "Curtain:turnOn": {"label": "Open curtain"},
    "Curtain:turnOff": {"label": "Close curtain"},
    "Curtain:pause": {"label": "Pause movement"},
    "Curtain:setPosition": {
        "label": "Move to position",
        "fields": (
            ParamField(key="index", label="Curtain", kind="number", default="0",
                       minimum=0, maximum=8,
                       help="Which curtain in a paired group. 0 unless grouped."),
            ParamField(key="mode", label="Mode", kind="select", default="ff",
                       options=(("ff", "Default"), ("0", "Performance"),
                                ("1", "Silent"))),
            ParamField(key="position", label="Position", kind="number",
                       minimum=0, maximum=100, unit="%",
                       help="0 is fully open, 100 is fully closed."),
        ),
    },
    "Curtain 3:turnOn": {"label": "Open curtain"},
    "Curtain 3:turnOff": {"label": "Close curtain"},
    "Curtain 3:pause": {"label": "Pause movement"},
    "Curtain 3:setPosition": {
        "label": "Move to position",
        "fields": (
            ParamField(key="index", label="Curtain", kind="number", default="0",
                       minimum=0, maximum=8,
                       help="Which curtain in a paired group. 0 unless grouped."),
            ParamField(key="mode", label="Mode", kind="select", default="ff",
                       options=(("ff", "Default"), ("0", "Performance"),
                                ("1", "Silent"))),
            ParamField(key="position", label="Position", kind="number",
                       minimum=0, maximum=100, unit="%",
                       help="0 is fully open, 100 is fully closed."),
        ),
    },
    "Smart Lock:lock": {"label": "Lock"},
    "Smart Lock:unlock": {"label": "Unlock"},
    "Air Conditioner:setAll": {
        "label": "Set temperature, mode and fan",
        "fields": (
            ParamField(key="temperature", label="Temperature", kind="number",
                       default="26", minimum=16, maximum=30, unit="°C"),
            ParamField(key="mode", label="Mode", kind="select", default="2",
                       options=(("1", "Auto"), ("2", "Cool"), ("3", "Dry"),
                                ("4", "Fan"), ("5", "Heat"))),
            ParamField(key="fan_speed", label="Fan speed", kind="select",
                       default="1",
                       options=(("1", "Auto"), ("2", "Low"), ("3", "Medium"),
                                ("4", "High"))),
            ParamField(key="power_state", label="Power", kind="select",
                       default="on", options=(("on", "On"), ("off", "Off"))),
        ),
    },
}

# Device types that resolve to another type's command set, or to no commands.
# Copied verbatim from the pre-4.0.0 device_commands.py.
DEVICE_TYPE_ALIASES: dict[str, str] = {
    "Hub Mini": "_hub",
    "Hub 2": "_hub",
    "Hub 3": "_hub",
    "Hub Plus": "_hub",
    "AI Hub": "_hub",
    "Remote": "_no_commands",
    "Meter": "_no_commands",
    "Meter Plus": "_no_commands",
    "Outdoor Meter": "_no_commands",
    "Meter Pro": "_no_commands",
    "Meter Pro CO2": "_no_commands",
    "Motion Sensor": "_no_commands",
    "Contact Sensor": "_no_commands",
    "Presence Sensor": "_no_commands",
    "Water Leak Detector": "_no_commands",
    "Indoor Cam": "_no_commands",
    "Pan/Tilt Cam": "_no_commands",
    "Pan/Tilt Cam 2K": "_no_commands",
    "Pan/Tilt Cam Plus 2K": "_no_commands",
    "Pan/Tilt Cam Plus 3K": "_no_commands",
    "Home Climate Panel": "_no_commands",
    "Evaporative Humidifier": "Humidifier2",
    "Evaporative Humidifier (Auto-refill)": "Humidifier2",
    "Mini Robot Vacuum K10+": "K10+",
    "Mini Robot Vacuum K10+ Pro": "K10+ Pro",
    "Multitasking Household Robot K20+ Pro": "K20+ Pro",
    "Floor Cleaning Robot S10": "Floor Cleaning Robot S10",
    "Floor Cleaning Robot S20": "S20",
    "Robot Vacuum K11+": "K11+",
    "K10+ Pro Combo": "Robot Vacuum Cleaner K10+ Pro Combo",
    "LED Strip Light 3": "Strip Light 3",
}

PARAMETER_OPTION_LABELS: dict[str, dict[str, str]] = {
    "PowLevel": {
        "0": "0 - Quiet",
        "1": "1 - Standard",
        "2": "2 - Strong",
        "3": "3 - MAX",
    },
    "setNightLightMode": {"off": "Off", "1": "1 - Bright", "2": "2 - Dim"},
    "setWindMode": {
        "direct": "Direct",
        "natural": "Natural",
        "sleep": "Sleep",
        "baby": "Ultra Quiet (Baby)",
    },
    "selfClean": {"1": "1 - Wash mop", "2": "2 - Dry", "3": "3 - Terminate"},
}
```

Copy the remaining `PARAMETER_OPTION_LABELS` entries (`setMode:Relay Switch 1PM`, `setMode:Relay Switch 1`, `setMode:Smart Radiator Thermostat`, `setChildLock:Air Purifier VOC`, `setChildLock:Humidifier2`, `turnOn:Relay Switch 2PM`, `turnOff:Relay Switch 2PM`, `toggle:Relay Switch 2PM`) verbatim from the pre-rewrite `device_commands.py:945-1009` — retrieve them with `git show HEAD~1:device_commands.py` if already overwritten.

- [ ] **Step 4: Rewrite `device_commands.py`**

```python
"""Lookup layer over the generated command index and the hand-written overlay.

Public API is unchanged from 3.x for get_commands_for_device_type() and
get_parameter_label(); find_command() and resolve_command_type() are new.
"""

from __future__ import annotations

from dataclasses import replace

from .command_index import COMMAND_INDEX, IR_COMMAND_INDEX
from .command_overlay import (
    COMMAND_OVERLAY,
    DEVICE_TYPE_ALIASES,
    PARAMETER_OPTION_LABELS,
)
from .command_types import CommandDef, ParamField

# Commands the upstream IR table lists for every remote type except Others.
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

    resolved = DEVICE_TYPE_ALIASES.get(device_type, device_type)
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
    """
    if not is_infrared:
        found = find_command(device_type, command)
        return found.command_type if found else "command"

    if command in tuple(custom_buttons):
        return "customize"

    found = find_command(device_type, command, is_infrared=True)
    if found is not None:
        return found.command_type
    return "customize"


def get_parameter_label(command: str, value: str, device_type: str = "") -> str:
    """Return a human-readable label for a parameter option value."""
    device_key = f"{command}:{device_type}"
    if device_key in PARAMETER_OPTION_LABELS:
        return PARAMETER_OPTION_LABELS[device_key].get(value, value)
    if command in PARAMETER_OPTION_LABELS:
        return PARAMETER_OPTION_LABELS[command].get(value, value)
    return value
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_device_commands.py tests/test_ir_commands.py -v`
Expected: 20 passed.

`test_others_remote_has_no_standard_commands` passes because Task 6's generator drops upstream's `{user-defined button name}` placeholder row, so `Others` never becomes a key in `IR_COMMAND_INDEX` and `get_commands_for_device_type` returns `[]` for it. If this test fails, the placeholder filter did not run — regenerate the index.

- [ ] **Step 6: Run the whole suite to confirm nothing regressed**

Run: `.venv/bin/pytest -v`
Expected: all tests pass, including `tests/test_harness.py` (which now exercises the rewritten `device_commands.py`). If `test_loader_imports_existing_device_commands` fails because `Bot`'s command order changed, update its assertion to `assert "turnOn" in [c.command for c in commands]`.

- [ ] **Step 7: Commit**

```bash
git add command_overlay.py device_commands.py tests/test_device_commands.py tests/test_ir_commands.py tests/test_harness.py
git commit -m "feat: merge generated index with hand overlay; fix IR commandType resolution"
```

---

## Task 8: `service_generator.py` — naming and the alias map

**Files:**
- Create: `service_generator.py`
- Test: `tests/test_service_naming.py`

**Interfaces:**
- Consumes: `device_commands.get_commands_for_device_type`, `command_types.CommandDef`.
- Produces:
  - `slugify(text) -> str`
  - `GeneratedService(name, title, description, device_id, device_type, is_infrared, commands, command_def)` — frozen dataclass. `command_def is None` means a dropdown action; otherwise a single-command action.
  - `build_services(devices, *, ir_buttons=None, existing_aliases=None) -> tuple[list[GeneratedService], dict[str, str]]`

A device record is the dict `fetch_devices()` already produces: `{"device_id", "device_name", "device_type", "is_infrared"}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_service_naming.py`:

```python
from conftest import load_integration_module

sg = load_integration_module("service_generator")


def device(name, device_type, device_id, infrared=False):
    return {
        "device_id": device_id,
        "device_name": name,
        "device_type": device_type,
        "is_infrared": infrared,
    }


def test_slugify_basic():
    assert sg.slugify("Office Curtain") == "office_curtain"
    assert sg.slugify("Curtain Right") == "curtain_right"


def test_slugify_strips_punctuation_and_collapses_separators():
    assert sg.slugify("Bob's  \"TV\" (Den)") == "bobs_tv_den"
    assert sg.slugify("popIn Aladdin 2 (Hub3)") == "popin_aladdin_2_hub3"


def test_slugify_handles_non_ascii():
    assert sg.slugify("ボタン") == "device"
    assert sg.slugify("Café Light") == "caf_light"


def test_device_action_is_generated_for_controllable_device():
    services, _ = sg.build_services([device("Office Curtain", "Curtain", "E1")])
    names = [s.name for s in services]
    assert "office_curtain" in names


def test_parameterless_commands_live_in_the_dropdown_action():
    services, _ = sg.build_services([device("Office Curtain", "Curtain", "E1")])
    dropdown = next(s for s in services if s.name == "office_curtain")
    assert dropdown.command_def is None
    assert [c.command for c in dropdown.commands] == ["turnOn", "turnOff", "pause"]


def test_parameterized_command_gets_its_own_action():
    services, _ = sg.build_services([device("Office Curtain", "Curtain", "E1")])
    names = [s.name for s in services]
    assert "office_curtain_move_to_position" in names
    action = next(s for s in services if s.name == "office_curtain_move_to_position")
    assert action.command_def.command == "setPosition"


def test_no_action_for_devices_without_commands():
    services, _ = sg.build_services(
        [device("Hub Mini Living", "Hub Mini", "H1"),
         device("Mailbox Sensor", "Contact Sensor", "C1")]
    )
    assert services == []


def test_slug_collision_gets_device_id_suffix():
    services, _ = sg.build_services(
        [device("Curtain", "Curtain", "AAAA1111"),
         device("Curtain", "Curtain", "BBBB2222")]
    )
    dropdowns = sorted(s.name for s in services if s.command_def is None)
    assert dropdowns == ["curtain", "curtain_bbbb2222"]


def test_alias_map_records_every_generated_slug():
    services, aliases = sg.build_services([device("Office Curtain", "Curtain", "E1")])
    assert aliases["office_curtain"] == "E1"
    assert aliases["office_curtain_move_to_position"] == "E1"


def test_rename_keeps_the_old_slug_alive():
    """A renamed device must not break automations using the old action."""
    existing = {"office_curtain": "E1", "office_curtain_move_to_position": "E1"}
    services, aliases = sg.build_services(
        [device("Study Curtain", "Curtain", "E1")], existing_aliases=existing
    )
    names = [s.name for s in services]
    assert "study_curtain" in names
    assert "office_curtain" in names
    assert aliases["office_curtain"] == "E1"
    assert aliases["study_curtain"] == "E1"


def test_alias_for_a_removed_device_is_dropped():
    existing = {"old_gadget": "GONE1"}
    services, aliases = sg.build_services(
        [device("Office Curtain", "Curtain", "E1")], existing_aliases=existing
    )
    assert "old_gadget" not in aliases
    assert "old_gadget" not in [s.name for s in services]


def test_ir_others_remote_uses_registered_buttons_as_options():
    services, _ = sg.build_services(
        [device("Office Light", "Others", "02-1", infrared=True)],
        ir_buttons={"02-1": ["Bright", "Dim"]},
    )
    action = next(s for s in services if s.name == "office_light")
    assert [c.command for c in action.commands] == ["Bright", "Dim"]
    assert all(c.command_type == "customize" for c in action.commands)


def test_ir_custom_buttons_are_labelled_as_custom():
    services, _ = sg.build_services(
        [device("Living Room TV", "TV", "02-2", infrared=True)],
        ir_buttons={"02-2": ["Netflix"]},
    )
    action = next(s for s in services if s.name == "living_room_tv")
    labels = {c.command: c.label for c in action.commands}
    assert labels["Netflix"] == "Netflix (custom button)"
    assert labels["volumeAdd"] == "Volume up"


def test_ir_others_remote_with_no_buttons_still_gets_an_action():
    services, _ = sg.build_services(
        [device("Mini Lights", "Others", "02-3", infrared=True)]
    )
    action = next(s for s in services if s.name == "mini_lights")
    assert action.commands == ()
    assert action.is_infrared is True


def test_unknown_physical_device_type_gets_a_freeform_action():
    services, _ = sg.build_services([device("New Gadget", "Widget 9000", "W1")])
    action = next(s for s in services if s.name == "new_gadget")
    assert action.commands == ()
    assert action.is_infrared is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_service_naming.py -v`
Expected: collection error — no `service_generator.py`.

- [ ] **Step 3: Write the implementation**

Create `service_generator.py`:

```python
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

        standard = tuple(
            get_commands_for_device_type(device_type, is_infrared=is_infrared)
        )
        custom = _custom_button_commands(ir_buttons.get(device_id, ()))

        # Hubs, meters, cameras and the Remote expose no commands at all.
        # An unknown physical type still gets a free-form action so a newly
        # released SwitchBot device is never dead, and every IR remote gets one
        # because custom buttons can be typed inline.
        if _has_no_commands(device_type):
            continue

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
        source = next((s for s in services if s.device_id == device_id), None)
        if source is None:
            continue
        aliases[slug] = device_id
        services.append(replace(source, name=slug))

    return services, aliases


def _has_no_commands(device_type: str) -> bool:
    """True for hubs, meters, cameras and other command-less device types."""
    from .command_overlay import DEVICE_TYPE_ALIASES

    return DEVICE_TYPE_ALIASES.get(device_type) in ("_hub", "_no_commands")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_service_naming.py -v`
Expected: 16 passed.

If `test_rename_keeps_the_old_slug_alive` produces a parameterized action under the historical slug, make the `source` lookup prefer the dropdown service:

```python
        source = next(
            (s for s in services if s.device_id == device_id and s.command_def is None),
            None,
        )
```

- [ ] **Step 5: Commit**

```bash
git add service_generator.py tests/test_service_naming.py
git commit -m "feat: generate per-device action names with a persisted alias map"
```

---

## Task 9: `services.yaml` emission

**Files:**
- Modify: `service_generator.py`
- Test: `tests/test_yaml_emission.py`

**Interfaces:**
- Consumes: `GeneratedService` from Task 8.
- Produces: `render_services_yaml(generated, *, device_labels) -> str`.

The three existing actions (`get_devices`, `get_auth_headers`, `send_command`) must appear unchanged in every rendering, because the emitted file replaces `services.yaml` wholesale.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_yaml_emission.py`:

```python
import yaml

from conftest import load_integration_module

sg = load_integration_module("service_generator")
ct = load_integration_module("command_types")


def dropdown(name="office_curtain"):
    return sg.GeneratedService(
        name=name,
        title="SwitchBot: Office Curtain",
        description="Control Office Curtain (Curtain).",
        device_id="E1",
        device_name="Office Curtain",
        device_type="Curtain",
        is_infrared=False,
        commands=(
            ct.CommandDef(command="turnOn", label="Open curtain"),
            ct.CommandDef(command="turnOff", label="Close curtain"),
        ),
    )


def parameterized():
    return sg.GeneratedService(
        name="office_curtain_move_to_position",
        title="SwitchBot: Office Curtain - Move to position",
        description="Move the curtain.",
        device_id="E1",
        device_name="Office Curtain",
        device_type="Curtain",
        is_infrared=False,
        command_def=ct.CommandDef(
            command="setPosition",
            label="Move to position",
            encoding="csv",
            parameter="",
            fields=(
                ct.ParamField(key="position", label="Position", kind="number",
                              minimum=0, maximum=100, unit="%",
                              help="0 is open, 100 is closed."),
                ct.ParamField(key="mode", label="Mode", kind="select",
                              default="ff",
                              options=(("ff", "Default"), ("0", "Performance"))),
            ),
        ),
    )


def render(services, labels=("Office Curtain [Curtain]",)):
    return yaml.safe_load(
        sg.render_services_yaml(services, device_labels=list(labels))
    )


def test_existing_services_are_always_present():
    data = render([])
    assert "get_devices" in data
    assert "get_auth_headers" in data
    assert "send_command" in data


def test_send_command_keeps_its_five_fields():
    data = render([])
    assert set(data["send_command"]["fields"]) == {
        "device_name", "device_id", "command", "parameter", "command_type"
    }


def test_send_command_device_dropdown_uses_supplied_labels():
    data = render([], labels=("Office Curtain [Curtain]", "Door [Smart Lock]"))
    options = data["send_command"]["fields"]["device_name"]["selector"]["select"][
        "options"
    ]
    assert options == ["Office Curtain [Curtain]", "Door [Smart Lock]"]


def test_send_command_falls_back_to_text_without_devices():
    data = render([], labels=())
    assert data["send_command"]["fields"]["device_name"]["selector"] == {"text": None}


def test_dropdown_action_emits_labelled_select():
    data = render([dropdown()])
    options = data["office_curtain"]["fields"]["command"]["selector"]["select"][
        "options"
    ]
    assert options == [
        {"label": "Open curtain", "value": "turnOn"},
        {"label": "Close curtain", "value": "turnOff"},
    ]


def test_dropdown_action_has_name_and_description():
    data = render([dropdown()])
    assert data["office_curtain"]["name"] == "SwitchBot: Office Curtain"
    assert data["office_curtain"]["description"].startswith("Control Office Curtain")


def test_number_field_becomes_slider_with_bounds_and_unit():
    data = render([parameterized()])
    fields = data["office_curtain_move_to_position"]["fields"]
    assert fields["position"]["selector"]["number"] == {
        "min": 0, "max": 100, "unit_of_measurement": "%", "mode": "slider"
    }


def test_every_field_emits_a_human_name():
    """Without an explicit name, HA renders the raw key."""
    data = render([parameterized()])
    fields = data["office_curtain_move_to_position"]["fields"]
    assert fields["position"]["name"] == "Position"
    assert fields["mode"]["name"] == "Mode"


def test_field_help_becomes_the_description():
    data = render([parameterized()])
    fields = data["office_curtain_move_to_position"]["fields"]
    assert fields["position"]["description"] == "0 is open, 100 is closed."


def test_select_field_emits_default_and_options():
    data = render([parameterized()])
    mode = data["office_curtain_move_to_position"]["fields"]["mode"]
    assert mode["default"] == "ff"
    assert mode["selector"]["select"]["options"] == [
        {"label": "Default", "value": "ff"},
        {"label": "Performance", "value": "0"},
    ]


def test_field_without_default_is_required():
    data = render([parameterized()])
    fields = data["office_curtain_move_to_position"]["fields"]
    assert fields["position"]["required"] is True
    assert fields["mode"]["required"] is False


def test_ir_action_command_select_allows_custom_values():
    ir = sg.GeneratedService(
        name="office_light",
        title="SwitchBot: Office Light",
        description="Control Office Light (Others).",
        device_id="02-1",
        device_name="Office Light",
        device_type="Others",
        is_infrared=True,
        commands=(ct.CommandDef(command="Bright", label="Bright (custom button)",
                                command_type="customize"),),
    )
    data = render([ir])
    select = data["office_light"]["fields"]["command"]["selector"]["select"]
    assert select["custom_value"] is True


def test_physical_action_command_select_does_not_allow_custom_values():
    data = render([dropdown()])
    select = data["office_curtain"]["fields"]["command"]["selector"]["select"]
    assert select.get("custom_value") is not True


def test_ir_action_with_no_known_commands_uses_a_text_field():
    ir = sg.GeneratedService(
        name="mini_lights",
        title="SwitchBot: Mini Lights",
        description="Control Mini Lights (Others).",
        device_id="02-3",
        device_name="Mini Lights",
        device_type="Others",
        is_infrared=True,
        commands=(),
    )
    data = render([ir])
    assert "text" in data["mini_lights"]["fields"]["command"]["selector"]


def test_names_with_quotes_and_colons_round_trip():
    service = sg.GeneratedService(
        name="bobs_tv",
        title='SwitchBot: Bob\'s "TV": the sequel',
        description="Control it.",
        device_id="E9",
        device_name='Bob\'s "TV"',
        device_type="Others",
        is_infrared=True,
        commands=(ct.CommandDef(command="ボタン", label="ボタン (custom button)",
                                command_type="customize"),),
    )
    data = render([service])
    assert data["bobs_tv"]["name"] == 'SwitchBot: Bob\'s "TV": the sequel'
    options = data["bobs_tv"]["fields"]["command"]["selector"]["select"]["options"]
    assert options[0]["value"] == "ボタン"


def test_output_is_valid_yaml_for_a_mixed_set():
    text = sg.render_services_yaml(
        [dropdown(), parameterized()], device_labels=["Office Curtain [Curtain]"]
    )
    assert yaml.safe_load(text) is not None
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_yaml_emission.py -v`
Expected: `AttributeError: module has no attribute 'render_services_yaml'`.

- [ ] **Step 3: Add the renderer to `service_generator.py`**

Append these imports and functions:

```python
import yaml

from .command_types import ParamField

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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_yaml_emission.py -v`
Expected: 17 passed.

- [ ] **Step 5: Eyeball the real output**

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'tests')
from conftest import load_integration_module
sg = load_integration_module('service_generator')
devices = [
    {'device_id':'E1','device_name':'Office Curtain','device_type':'Curtain','is_infrared':False},
    {'device_id':'D1','device_name':'Door','device_type':'Smart Lock','is_infrared':False},
    {'device_id':'02-1','device_name':'Office Light','device_type':'Others','is_infrared':True},
    {'device_id':'H1','device_name':'Hub Mini Living','device_type':'Hub Mini','is_infrared':False},
]
services, aliases = sg.build_services(devices, ir_buttons={'02-1':['Bright','Dim']})
print(sg.render_services_yaml(services, device_labels=['Office Curtain [Curtain]']))
print('aliases:', aliases)
"
```

Expected: valid YAML with `office_curtain`, `office_curtain_move_to_position`, `door`, `office_light`, and no `hub_mini_living`.

- [ ] **Step 6: Commit**

```bash
git add service_generator.py tests/test_yaml_emission.py
git commit -m "feat: render generated services.yaml with yaml.safe_dump"
```

---

## Task 10: Wire the generator into the integration runtime

**Files:**
- Modify: `services.py:53-168` (cache refresh and YAML write), `services.py:215-265` (`_resolve_command`), `services.py:301-431` (send path and registration), `__init__.py:31-38`
- Test: verified by the maintainer in a live Home Assistant. No pytest — these modules import `homeassistant`.

**Interfaces:**
- Consumes: `service_generator.build_services/render_services_yaml`, `command_types.encode_parameter/ParameterError`, `device_commands.find_command/resolve_command_type`.
- Produces: `_async_send(hass, entry, device, command, parameter, command_type) -> dict`; `async_regenerate_services(hass) -> None`; `DATA_GENERATED_SERVICES`, `DATA_IR_BUTTONS` keys in `hass.data[DOMAIN]`.

- [ ] **Step 1: Extract the shared send path**

In `services.py`, add above `async_send_command`:

```python
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
```

Then replace the body of `async_send_command` (currently `services.py:325-335`) so the `try/except` block around `async_request` becomes:

```python
    body = await _async_send(hass, entry, device, command, parameter, command_type)
```

Leave the rest of `async_send_command` — including its response dict and `_resolve_command` call — untouched.

- [ ] **Step 2: Add the IR button memory**

Add to `services.py`:

```python
DATA_GENERATED_SERVICES = "generated_services"
DATA_IR_BUTTONS = "ir_buttons"
CONF_IR_BUTTONS = "ir_buttons"


def get_ir_buttons(entry: ConfigEntry) -> dict[str, list[str]]:
    """Registered custom IR button names, keyed by device ID."""
    return dict(entry.options.get(CONF_IR_BUTTONS, {}))


async def _async_remember_ir_button(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str, command: str
) -> None:
    """Remember a custom button name the API accepted, then regenerate."""
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
    await async_regenerate_services(hass)
```

Note: names are appended verbatim. No case folding, no stripping.

- [ ] **Step 3: Replace the YAML writer with the generator**

Replace `_write_services_yaml()` (`services.py:123-168`) entirely:

```python
def _write_services_yaml_blocking(content: str) -> None:
    """Write services.yaml. Runs in an executor - never on the event loop."""
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
```

Add `CONF_SERVICE_ALIASES = "service_aliases"` beside `CONF_IR_BUTTONS`, and at the top of `services.py`:

```python
from .command_types import ParameterError, encode_parameter
from .device_commands import (
    CommandDef,
    find_command,
    get_commands_for_device_type,
    resolve_command_type,
)
from .service_generator import GeneratedService, build_services, render_services_yaml
```

- [ ] **Step 4: Register the generated services**

Add to `services.py`:

```python
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
```

- [ ] **Step 5: Call the generator from the refresh path**

In `async_refresh_device_cache()`, replace the `_write_services_yaml(...)` call (`services.py:116`) with nothing, and in `__init__.py`'s `async_setup_entry`, insert `await async_regenerate_services(hass)` immediately after `await async_reregister_send_command(hass)`:

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SwitchBot API from a config entry."""
    _cleanup_deprecated_entities(hass, entry)
    await async_refresh_device_cache(hass)
    await async_setup_services(hass)
    await async_reregister_send_command(hass)
    await async_regenerate_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

Add `async_regenerate_services` to the import list in `__init__.py:11-16`.

Regeneration runs unconditionally on setup because HACS overwrites the installed directory on update, taking the generated `services.yaml` with it.

- [ ] **Step 6: Regenerate on the refresh button and on `get_devices`**

In `button.py`'s `async_press` (`button.py:61-66`), add `await async_regenerate_services(self._hass)` after `async_reregister_send_command`, importing it from `.services`. In `async_get_devices` (`services.py:280`), add the same call after `await async_refresh_device_cache(hass)`.

- [ ] **Step 7: Tear down generated services on unload**

In `async_unload_services()` (`services.py:419-431`), before popping `hass.data`:

```python
    for name in hass.data.get(DOMAIN, {}).get(DATA_GENERATED_SERVICES, ()):
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
```

- [ ] **Step 8: Fix `_resolve_command`'s IR handling**

In `_resolve_command()` (`services.py:240-246`), replace the `command_type` block:

```python
    command_type = call_data.get(ATTR_COMMAND_TYPE, "")
    if not command_type:
        command_type = resolve_command_type(
            device_type,
            raw_command,
            is_infrared=is_infrared,
            custom_buttons=tuple(custom_buttons),
        )
```

Pass `custom_buttons` into `_resolve_command` from `async_send_command`:

```python
    entry_buttons = get_ir_buttons(entry).get(device["device_id"], [])
    command, parameter, command_type = _resolve_command(
        device, call.data, custom_buttons=entry_buttons
    )
```

and change the signature to
`def _resolve_command(device, call_data, *, custom_buttons=()) -> tuple[str, str | dict, str]:`.

An explicit `command_type` supplied by the caller still wins, so existing automations that set it keep their behaviour.

- [ ] **Step 9: Verify in a live Home Assistant**

Copy the integration into `config/custom_components/switchbot_api/` and restart HA. Confirm:
1. **Settings -> Devices & Services** shows SwitchBot API loaded with no errors.
2. `config/home-assistant.log` contains no "blocking call" warning and no traceback from `switchbot_api`.
3. **Developer Tools -> Actions** lists `SwitchBot: <device>` for each controllable device and nothing for hubs, meters or the Remote.
4. `SwitchBot: Office Curtain` shows a command dropdown reading "Open curtain" / "Close curtain" / "Pause movement".
5. `SwitchBot: Office Curtain - Move to position` shows a Position slider, a Mode dropdown and a Curtain box.
6. Calling it at position 50 actually moves the curtain, and the response shows `parameter: "0,ff,50"`.
7. `switchbot_api.send_command` still works exactly as before with a hand-written command.
8. `cat config/custom_components/switchbot_api/services.yaml` is valid YAML starting with the generated-file header.

- [ ] **Step 10: Commit**

```bash
git add services.py __init__.py button.py services.yaml
git commit -m "feat: register generated per-device actions at runtime"
```

---

## Task 11: IR custom button registration in the options flow

**Files:**
- Modify: `config_flow.py:121-168`, `translations/en.json`
- Test: `tests/test_options_merge.py` (pure merge helper), plus live verification

**Interfaces:**
- Consumes: `services.CONF_IR_BUTTONS`, `services.get_ir_buttons`, `services.async_regenerate_services`.
- Produces: `merge_ir_buttons(options, device_id, names) -> dict` in `service_generator.py` — pure, unit tested; the flow calls it.

- [ ] **Step 1: Write the failing test for the merge helper**

Create `tests/test_options_merge.py`:

```python
from conftest import load_integration_module

sg = load_integration_module("service_generator")


def test_merge_preserves_unrelated_options():
    """Regression: async_create_entry replaces options wholesale."""
    options = {"service_aliases": {"office_curtain": "E1"}}
    merged = sg.merge_ir_buttons(options, "02-1", ["Bright", "Dim"])
    assert merged["service_aliases"] == {"office_curtain": "E1"}
    assert merged["ir_buttons"]["02-1"] == ["Bright", "Dim"]


def test_merge_preserves_other_devices_buttons():
    options = {"ir_buttons": {"02-1": ["Bright"], "02-2": ["Netflix"]}}
    merged = sg.merge_ir_buttons(options, "02-1", ["Bright", "Dim"])
    assert merged["ir_buttons"]["02-2"] == ["Netflix"]


def test_merge_does_not_mutate_the_input():
    options = {"ir_buttons": {"02-1": ["Bright"]}}
    sg.merge_ir_buttons(options, "02-1", ["Dim"])
    assert options["ir_buttons"]["02-1"] == ["Bright"]


def test_merge_strips_blank_lines_and_surrounding_whitespace():
    merged = sg.merge_ir_buttons({}, "02-1", ["  Bright  ", "", "Dim", "   "])
    assert merged["ir_buttons"]["02-1"] == ["Bright", "Dim"]


def test_merge_preserves_case_exactly():
    merged = sg.merge_ir_buttons({}, "02-1", ["NetFLIX", "bright"])
    assert merged["ir_buttons"]["02-1"] == ["NetFLIX", "bright"]


def test_merge_deduplicates_while_keeping_first_order():
    merged = sg.merge_ir_buttons({}, "02-1", ["Bright", "Dim", "Bright"])
    assert merged["ir_buttons"]["02-1"] == ["Bright", "Dim"]


def test_empty_list_removes_the_device_entry():
    merged = sg.merge_ir_buttons({"ir_buttons": {"02-1": ["Bright"]}}, "02-1", [])
    assert "02-1" not in merged.get("ir_buttons", {})


def test_parse_button_lines_splits_on_newlines():
    assert sg.parse_button_lines("Bright\nDim\n\nNight") == ["Bright", "Dim", "Night"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_options_merge.py -v`
Expected: `AttributeError: module has no attribute 'merge_ir_buttons'`.

- [ ] **Step 3: Add the helpers to `service_generator.py`**

```python
CONF_IR_BUTTONS = "ir_buttons"


def parse_button_lines(text: str) -> list[str]:
    """Split a textarea value into button names, preserving case."""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def merge_ir_buttons(
    options: Mapping[str, Any], device_id: str, names: Iterable[str]
) -> dict[str, Any]:
    """Return a new options dict with this device's button names replaced.

    Merges rather than replaces: OptionsFlow.async_create_entry overwrites the
    whole options dict, which would otherwise erase service_aliases.
    """
    cleaned: list[str] = []
    for name in names:
        stripped = name.strip()
        if stripped and stripped not in cleaned:
            cleaned.append(stripped)

    buttons = {
        key: list(value)
        for key, value in dict(options.get(CONF_IR_BUTTONS, {})).items()
    }
    if cleaned:
        buttons[device_id] = cleaned
    else:
        buttons.pop(device_id, None)

    merged = dict(options)
    if buttons:
        merged[CONF_IR_BUTTONS] = buttons
    else:
        merged.pop(CONF_IR_BUTTONS, None)
    return merged
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_options_merge.py -v`
Expected: 8 passed.

- [ ] **Step 5: Turn the options flow into a menu**

Replace `SwitchBotAuthOptionsFlowHandler` in `config_flow.py:121-168`:

```python
class SwitchBotAuthOptionsFlowHandler(config_entries.OptionsFlow):
    """Device summary and custom IR button registration."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._ir_device_id: str | None = None
        self._ir_devices: list[dict[str, Any]] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Offer the device summary or the IR button editor."""
        return self.async_show_menu(
            step_id="init", menu_options=["devices", "ir_buttons"]
        )

    async def async_step_devices(self, user_input: dict[str, Any] | None = None):
        """Display the device summary."""
        if user_input is not None:
            return self.async_create_entry(data=dict(self.config_entry.options))

        try:
            result = await fetch_devices(self.hass, self.config_entry)
        except SwitchBotApiError as exc:
            result = {
                "device_count": 0,
                "physical_device_count": 0,
                "infrared_remote_count": 0,
                "devices": [],
            }
            _LOGGER.warning("Could not fetch devices in options flow: %s", exc)

        physical = []
        infrared = []
        for device in result.get("devices", []):
            line = (
                f"• **{device['device_name']}** ({device['device_type']}) "
                f"`{device['device_id']}`"
            )
            if device.get("is_infrared"):
                infrared.append(line)
            else:
                physical.append(line)

        sections = []
        if physical:
            sections.append("**Physical devices:**\n" + "\n".join(physical))
        if infrared:
            sections.append("**Infrared remotes:**\n" + "\n".join(infrared))
        if not sections:
            sections.append("No devices found in this SwitchBot account.")

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_count": str(result["device_count"]),
                "physical_device_count": str(result["physical_device_count"]),
                "infrared_remote_count": str(result["infrared_remote_count"]),
                "devices": "\n\n".join(sections),
            },
        )

    async def async_step_ir_buttons(self, user_input: dict[str, Any] | None = None):
        """Pick which infrared remote to edit."""
        try:
            result = await fetch_devices(self.hass, self.config_entry)
        except SwitchBotApiError:
            return self.async_abort(reason="cannot_connect")

        self._ir_devices = [
            d for d in result.get("devices", []) if d.get("is_infrared")
        ]
        if not self._ir_devices:
            return self.async_abort(reason="no_ir_devices")

        if user_input is not None:
            self._ir_device_id = user_input["device_id"]
            return await self.async_step_ir_edit()

        options = [
            {"value": d["device_id"], "label": f"{d['device_name']} [{d['device_type']}]"}
            for d in self._ir_devices
        ]
        return self.async_show_form(
            step_id="ir_buttons",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def async_step_ir_edit(self, user_input: dict[str, Any] | None = None):
        """Edit one remote's custom button names."""
        device_id = self._ir_device_id
        device = next(
            (d for d in self._ir_devices if d["device_id"] == device_id), None
        )
        device_name = device["device_name"] if device else device_id

        if user_input is not None:
            names = parse_button_lines(user_input.get("buttons", ""))
            merged = merge_ir_buttons(self.config_entry.options, device_id, names)
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=merged
            )
            await async_regenerate_services(self.hass)
            return self.async_create_entry(data=merged)

        current = get_ir_buttons(self.config_entry).get(device_id, [])
        return self.async_show_form(
            step_id="ir_edit",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "buttons", default="\n".join(current)
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
            description_placeholders={"device_name": device_name},
        )
```

Add to `config_flow.py`'s imports:

```python
from homeassistant.helpers import selector

from .service_generator import merge_ir_buttons, parse_button_lines
from .services import async_regenerate_services, fetch_devices, get_ir_buttons
```

- [ ] **Step 6: Add the translation strings**

In `translations/en.json`, replace the `options` object with:

```json
  "options": {
    "step": {
      "init": {
        "title": "SwitchBot API",
        "menu_options": {
          "devices": "View device list",
          "ir_buttons": "Custom infrared buttons"
        }
      },
      "devices": {
        "title": "SwitchBot devices",
        "description": "Found **{device_count}** devices ({physical_device_count} physical, {infrared_remote_count} infrared remotes).\n\n{devices}\n\nPress **Refresh device list** on the device page to update the cached device list."
      },
      "ir_buttons": {
        "title": "Custom infrared buttons",
        "description": "Pick the infrared remote whose custom buttons you want to register.",
        "data": {
          "device_id": "Infrared remote"
        }
      },
      "ir_edit": {
        "title": "Buttons for {device_name}",
        "description": "Enter the custom button names exactly as they appear in the SwitchBot app, one per line. Names are case-sensitive. These become a dropdown on this remote's action.",
        "data": {
          "buttons": "Button names"
        }
      }
    },
    "abort": {
      "cannot_connect": "Could not connect to the SwitchBot API",
      "no_ir_devices": "No infrared remotes found in this SwitchBot account."
    }
  },
```

- [ ] **Step 7: Verify in a live Home Assistant**

Restart HA, then:
1. **Settings -> Devices & Services -> SwitchBot API -> Configure** shows a two-option menu.
2. *View device list* shows the same summary as before.
3. *Custom infrared buttons* lists your three `Others` remotes.
4. Selecting `Office Light` shows an empty multi-line box. Enter two real button names and submit.
5. **Developer Tools -> Actions -> SwitchBot: Office Light** now shows those names in a dropdown that still accepts typed values.
6. Calling it with a registered name actuates the device.
7. Call it with a *different* real button name typed inline; it works, and that name then appears in the dropdown without you registering it.
8. Reopen Configure -> *Custom infrared buttons* -> `Office Light`: the box is pre-filled, and `service_aliases` survived — confirm with
   `grep -o '"service_aliases":[^}]*}' config/.storage/core.config_entries`.

- [ ] **Step 8: Commit**

```bash
git add config_flow.py service_generator.py translations/en.json tests/test_options_merge.py
git commit -m "feat: register custom infrared button names via the options flow"
```

---

## Task 12: Documentation and release

**Files:**
- Modify: `README.md`, `manifest.json`
- Create: `tools/README.md`

- [ ] **Step 1: Bump the version**

```bash
.venv/bin/python -c "
import json, pathlib
p = pathlib.Path('manifest.json')
m = json.loads(p.read_text())
m['version'] = '4.0.0'
p.write_text(json.dumps(m, indent=2) + '\n')
print(m['version'])
"
```

- [ ] **Step 2: Document the generator**

Create `tools/README.md`:

```markdown
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
```

- [ ] **Step 3: Update the main README**

In `README.md`, after the "What It Does" list, insert:

```markdown
### Per-device actions (4.0.0+)

Every controllable device in your account gets its own action with a
plain-English command dropdown — no command strings to look up:

```yaml
action: switchbot_api.office_curtain
data:
  command: turnOn
```

Commands needing input get their own action with typed fields, and the API's
parameter string is assembled for you:

```yaml
action: switchbot_api.office_curtain_move_to_position
data:
  position: 80
  mode: ff
  index: 0
# sends parameter "0,ff,80"
```

Hubs, meters and sensors generate no actions, since the API exposes no commands
for them. Renaming a device in the SwitchBot app adds a new action and keeps the
old one working, so existing automations don't break.

`switchbot_api.send_command` is unchanged and remains the escape hatch for
device types the command index doesn't know yet.

### Custom infrared buttons

The SwitchBot API cannot list the custom buttons you've configured in the app —
`infraredRemoteList` returns only device ID, name, remote type and hub ID. Register
them once under **Settings → Devices & Services → SwitchBot API → Configure →
Custom infrared buttons**, one name per line, exactly as they appear in the app
(names are case-sensitive). They then appear as a dropdown on that remote's
action, sent with `commandType: customize`.

Any custom button name the API accepts is also remembered automatically, so a
name you type inline once appears in the dropdown afterwards.
```

Also update the "How It Works" numbered list: step 4 should describe the
generated per-device actions rather than manual command entry.

- [ ] **Step 4: Run the whole suite one last time**

Run: `.venv/bin/pytest -v`
Expected: every test passes. Record the count.

- [ ] **Step 5: Confirm no HA imports leaked into tested modules**

```bash
grep -l "^from homeassistant\|^import homeassistant" \
  command_types.py command_index.py command_overlay.py \
  device_commands.py service_generator.py tools/*.py
```

Expected: no output. Any hit breaks the no-HA testing constraint.

- [ ] **Step 6: Commit**

```bash
git add README.md tools/README.md manifest.json
git commit -m "docs: document generated actions and IR button registration for 4.0.0"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| D1 per-device actions | 8, 9, 10 |
| D2 alias map | 8 (`test_rename_keeps_the_old_slug_alive`) |
| D3 hybrid parameter presentation | 8 (simple vs parameterized split), 9 (field emission) |
| D4 generator + overlay | 4, 5, 6, 7 |
| D5 IR buttons | 7, 10 (auto-remember), 11 (options flow) |
| D6 `send_command` untouched | 9 (`test_send_command_keeps_its_five_fields`), 10 Step 1 |
| D7 pytest + smoke test | 2, and the live-verification steps in 10 and 11 |
| Data model (`ParamField`/`CommandDef`/encodings) | 3 |
| Generator report of overlay candidates | 6 |
| Device types generating nothing | 8 |
| Unknown device types | 8 |
| IR command-type resolution | 7 |
| `custom_value: true` combo box | 9 |
| Verbatim case-sensitive button names | 7, 11 |
| Options merge preserving `service_aliases` | 11 |
| Bug 1: blocking I/O | 10 Step 3 |
| Bug 2: unsafe YAML | 9 |
| Bug 3: `customize` for `Others` only | 7, 10 Step 8 |
| Bug 4: AC mode `0` | 5, 7 (overlay lists modes 1-5 with 0/1 collapsed to 1) |
| Restart unknown | 1 |
| Build order | Task order matches the spec's sequence |
| Release 4.0.0 | 12 |

No spec requirement is unaddressed.

**Type consistency check:** `ParamField` uses `minimum`/`maximum` in every task (Tasks 3, 5, 7, 9) — never `min`/`max`, which appear only as emitted YAML keys. `CommandDef.display_label` is defined in Task 3 and used in Tasks 8 and 9. `build_services` returns `(list[GeneratedService], dict[str, str])` in Tasks 8, 10 and 11. `encode_parameter(command_def, supplied)` keeps that argument order in Tasks 3 and 10. `get_commands_for_device_type(device_type, *, is_infrared)` keeps its 3.x signature in Tasks 7 and 8. `CONF_IR_BUTTONS` is `"ir_buttons"` in both `services.py` (Task 10) and `service_generator.py` (Task 11).

**Known ordering constraint:** Task 11's `config_flow.py` imports `async_regenerate_services` and `get_ir_buttons` from `services.py`, both added in Task 10. Task 10 must land first.
