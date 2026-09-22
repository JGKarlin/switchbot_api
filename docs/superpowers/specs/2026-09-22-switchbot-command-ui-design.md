# Human-readable, auto-generated device commands

**Date:** 2026-09-22
**Status:** Approved design, not yet implemented
**Target version:** 4.0.0

## Problem

To control a device today the user calls `switchbot_api.send_command` and types
`command`, `parameter` and `command_type` as free text (`services.yaml:26-38`).
Choosing the right values means reading the SwitchBot API documentation and
knowing, for example, that a curtain half-open is `setPosition` with the string
`0,ff,80`. The device picker is friendly; everything after it is not.

The integration already holds the knowledge needed to fix this.
`device_commands.py` is a hand-written index of ~60 physical device types and 9
infrared remote types, each command carrying a prose `parameter_description` and
sometimes `parameter_options`. `_resolve_command()` (`services.py:215`) consults
it to infer `command_type` and default parameters. None of it reaches the UI.

Two things are missing:

1. The index is never surfaced as selectable, human-language choices.
2. The index is hand-maintained, so it drifts from SwitchBot's own documentation
   as new devices ship.

## Goals

- Pick a device and a command in plain English, from dropdowns, without
  consulting any documentation.
- Supply command parameters through typed fields (sliders, mode dropdowns) that
  are encoded into the API's wire format automatically.
- Derive the command index from SwitchBot's published documentation rather than
  by hand.
- Break nothing: every existing automation keeps working untouched.

## Non-goals

Explicitly out of scope, to be revisited separately if wanted:

- Scenes (`/v1.1/scenes`, `/v1.1/scenes/{id}/execute`).
- Device status polling and state entities (`/v1.1/devices/{id}/status`).
- Webhooks.
- Exposing SwitchBot devices as native Home Assistant entities
  (`cover`, `climate`, `light`). That would overlap with the official
  `switchbot_cloud` integration this project exists to work around.

## Decisions

Each decision below was resolved explicitly during design.

### D1 — One generated action per device

Home Assistant builds the "Perform action" form statically from `services.yaml`.
There is no conditional field display: `filter:` keys off a target entity's
features, not off the value of a sibling field. A single action therefore cannot
narrow its `command` dropdown to the device chosen in the same form.

Generating one action per detected device is the only way to get a genuinely
dependent dropdown in the normal action picker, and it extends a pattern the
codebase already uses — `_write_services_yaml()` (`services.py:123`) already
rewrites `services.yaml` at runtime to inject the device-name dropdown.

Rejected: a union dropdown across all devices (cannot prevent invalid
device/command pairs); a wizard under Configure (not inline in the automation
editor); native entities (out of scope, see Non-goals).

### D2 — Name-derived action names with a persisted alias map

Action names are slugged from the device name, so automation YAML reads
`switchbot_api.office_curtain`. Because SwitchBot device names are renameable,
an alias map `{slug: device_id}` is persisted in `entry.options`. Regeneration
registers the current slug **and** every historical slug whose device still
exists, so a rename adds an action instead of breaking one.

Rejected: accepting rename breakage (silent automation failure); device-ID
slugs with translated display labels (opaque YAML — cannot tell which device an
automation touches without a lookup).

### D3 — Simple commands in a dropdown, parameterized commands get their own action

Since all fields of an action render at once, putting every parameter of every
command on one per-device action would show a position slider while "Turn on" is
selected.

- Commands taking no parameter (`turnOn`, `turnOff`, `lock`, `pause`) collapse
  into a single per-device action with one `command` dropdown and no parameter
  fields at all.
- Each command that requires input gets its own action with exactly the fields
  that command needs.

For the reference account (13 devices) this is ~7 device actions plus ~4
parameterized ones.

Rejected: one action per device per command (~19 actions, noisy picker); one
action per device showing all fields (irrelevant inputs always visible).

### D4 — Build-time generator over upstream docs, plus a reviewed overlay

The SwitchBot API exposes no command-discovery endpoint. The documented v1.1
surface is `/devices`, `/devices/{id}/status`, `/devices/{id}/commands`,
`/scenes`, `/scenes/{id}/execute` and the webhook endpoints. "Auto-index"
therefore cannot mean querying the API.

It can mean parsing the documentation. `OpenWonderLabs/SwitchBotAPI` publishes 84
per-device markdown files under `devices/**/*.md`, each containing a
`## Control Commands` table with columns
`deviceType | commandType | Command | command parameter | Description`, plus a
combined table for virtual infrared remotes in
`devices/others/virtual-infrared-remote-devices.md`.

A build-time script parses these into a committed Python module. A hand-written
overlay supplies friendly labels and any field schema the parser cannot derive
confidently. Regenerating produces a reviewable git diff.

Rejected: runtime fetching and parsing inside Home Assistant (network dependency
for static data, breaks offline, fragile against upstream restructuring);
generator with no overlay (some commands would present worse than they need to);
continued hand-maintenance (does not address index drift).

### D5 — IR custom buttons registered once, then auto-remembered

`infraredRemoteList` returns only `deviceId`, `deviceName`, `remoteType` and
`hubDeviceId`. Custom button names exist solely in the user's SwitchBot app and
cannot be discovered through the API. They are collected once through the
options flow and thereafter remembered automatically whenever a `customize`
command succeeds. See "Infrared remotes" below.

### D6 — `send_command` is left untouched

The existing action keeps its name, fields and behaviour. It is documented as
the raw escape hatch for device types the index does not yet know and for
sending a command verbatim. All new actions are purely additive.

### D7 — Verification by pytest plus a manual smoke test

Pure logic (parsing, schema derivation, naming, encoding, YAML safety) is
covered by pytest that runs without Home Assistant installed. Whether the action
picker renders the result correctly is confirmed by the maintainer in a live
Home Assistant.

Rejected: `pytest-homeassistant-custom-component` (heavier dependency, pins to
HA versions) — reconsider if the integration later grows entity platforms.

## Architecture

```
tools/generate_command_index.py        build time; never imported by HA
        |  fetch 84 upstream devices/**/*.md + the virtual IR remote table
        |  parse "## Control Commands"; derive ParamField schemas
        v
command_index.py                       generated, committed, reviewable
        +
command_overlay.py                     hand-written labels + fallback schemas
        v
device_commands.py                     merges both; public lookup API
        v
service_generator.py                   devices x index -> services.yaml + handlers
        v
services.py / __init__.py / config_flow.py
```

`hacs.json` sets `content_in_root: true`, so the repository root *is* the shipped
integration directory and `tools/` ships to users. It is roughly 8 KB of Python
that Home Assistant never imports. Relocating the integration into
`custom_components/switchbot_api/` would avoid this but would break every
existing manual installation, so it is not worth doing.

## Data model

`device_commands.py` gains a structured parameter schema. This is what makes
generated UI fields possible; the current `parameter_description` string holds
the same information in prose that only a human can act on.

```python
@dataclass(frozen=True)
class ParamField:
    key: str                              # "position"
    label: str                            # "Position"
    kind: str                             # number | select | boolean | text
    required: bool = True
    default: str | int | None = None
    min: int | None = None                # number only
    max: int | None = None                # number only
    unit: str | None = None               # number only, e.g. "%"
    options: tuple[tuple[str, str], ...] = ()   # select only, (value, label)
    help: str = ""                        # inline description

@dataclass(frozen=True)
class CommandDef:
    command: str                          # "setPosition"
    label: str                            # "Move to position"
    description: str = ""
    command_type: str = "command"
    parameter: str = "default"            # literal, used when fields is empty
    fields: tuple[ParamField, ...] = ()
    encoding: str = "none"                # none | csv | json | scalar
```

`encoding` defines how field values become the API's `parameter` value:

| encoding | Produces | Example |
| --- | --- | --- |
| `none` | the literal `parameter` | `"default"` |
| `csv` | field values joined by `,` in declaration order | `setPosition` -> `"0,ff,80"` |
| `json` | an object keyed by field `key` | `Humidifier2.setMode` -> `{"mode": 7, "targetHumidify": 50}` |
| `scalar` | the single field's value | `SetChannel` -> `"15"` |

A field the caller omits is filled from its `default` before encoding, so `csv`
always emits every positional part and `json` always emits every key. A field
with neither a value nor a default is a validation error, raised as
`ServiceValidationError` rather than being encoded as an empty part — sending
`",ff,80"` to the API would fail opaquely.

`get_commands_for_device_type(device_type, *, is_infrared)` keeps its current
signature so `_resolve_command()` continues to work during and after migration.

The existing `device_commands.py` content is not discarded: its
`parameter_description` prose, `parameter_options` and `PARAMETER_OPTION_LABELS`
are precisely the material `command_overlay.py` needs, and it is the seed for
that file.

## Generator

`tools/generate_command_index.py`:

1. Fetch the upstream tree listing; download every `devices/**/*.md`.
2. Parse each `## Control Commands` table into rows of
   `(device_type, command_type, command, parameter_spec, description)`.
   Upstream tables use a blank leading cell to mean "same device type as the row
   above" (see the TV / IPTV / Set Top Box block); the parser carries the value
   forward.
3. Normalize device type strings. Upstream is internally inconsistent —
   `devices/curtains-blinds/curtain-3.md` documents `deviceType: Curtain3` in
   its device-list table but `Curtain 3` in its command table. Normalization
   resolves against the values `/v1.1/devices` actually returns, backed by an
   explicit alias table. **A device type that cannot be reconciled is a hard
   error that fails the generator run**, never a silently dropped device.
4. Derive `ParamField` schemas heuristically from the parameter and description
   columns:
   - `default` -> no fields, `encoding="none"`
   - a range such as `0~100` or `1-100` -> `number` with `min`/`max`
   - a positional spec such as ``index0,mode0,position0<br />e.g. `0,ff,80` ``
     -> `csv` with one field per part
   - an enumeration such as `mode: 0 (Performance Mode), 1 (Silent Mode),
     ff (default mode)` -> `select` options with labels
   - a JSON body such as `{"mode": int, "targetHumidify": int}` -> `json`
     encoding with one field per key
   - `true`/`false` -> `boolean`
   - anything unrecognized -> a single `text` field carrying the upstream
     description as `help`
5. Write `command_index.py` and print a report: commands parsed, schemas
   auto-derived, and an explicit list of commands that fell back to `text` and
   are therefore candidates for the overlay.

Output is a Python module rather than JSON so that runtime cost is a plain
import with no file I/O, and so the committed data is type-checkable.

Generating from upstream also corrects existing drift. The current hand-written
Air Conditioner entry documents `mode: 1=auto`, while upstream states
`0/1 (auto)` — mode `0` is currently undocumented in this integration.

### Overlay

`command_overlay.py` is hand-written, keyed `"{device_type}:{command}"`, and
merged over the generated index at import time. It supplies human command labels
("Move to position" for `setPosition`), friendlier field labels, and schemas for
commands the parser left as `text`. Keeping it separate from the generated file
means regeneration never clobbers hand-written work.

## Service generation

`service_generator.py` turns the cached device list plus the merged index into
the generated `services.yaml` and the registered handlers.

### Naming

- Device action: `slugify(device_name)` -> `office_curtain`. Collisions get a
  short device-ID suffix.
- Parameterized command action: `f"{device_slug}_{slugify(command_label)}"` ->
  `office_curtain_move_to_position`.
- `entry.options["service_aliases"]` maps `{slug: device_id}`. On every
  regeneration, register the current slug for each device plus any historical
  slug whose `device_id` is still present in the account. Entries whose device
  has disappeared are dropped.

### Generated `services.yaml`

```yaml
office_curtain:
  name: "SwitchBot: Office Curtain"
  description: "Control Office Curtain (Curtain)."
  fields:
    command:
      required: true
      selector:
        select:
          options:
            - {label: "Open curtain", value: turnOn}
            - {label: "Close curtain", value: turnOff}
            - {label: "Pause movement", value: pause}

office_curtain_move_to_position:
  name: "SwitchBot: Office Curtain - Move to position"
  description: "Move Office Curtain to a specific position."
  fields:
    position:
      name: "Position"
      description: "0 is fully open, 100 is fully closed."
      required: true
      selector:
        number: {min: 0, max: 100, unit_of_measurement: "%", mode: slider}
    mode:
      name: "Mode"
      description: "Movement mode."
      required: false
      default: "ff"
      selector:
        select:
          options:
            - {label: "Default", value: "ff"}
            - {label: "Performance", value: "0"}
            - {label: "Silent", value: "1"}
    index:
      name: "Curtain"
      description: "Which curtain in a paired group. 0 unless grouped."
      required: false
      default: "0"
      selector:
        number: {min: 0, max: 8, mode: box}
```

Every field emits an explicit `name:` and `description:`, mapped from
`ParamField.label` and `ParamField.help`. Without `name:` Home Assistant renders
the raw field key ("position"), which would defeat the point of the feature.

Field `kind` maps to selectors as: `number` -> `number` (slider when bounded,
box otherwise), `select` -> `select` with `{label, value}` options, `boolean` ->
`boolean`, `text` -> `text`.

The field order in the emitted YAML is presentation order, chosen most-important
first, and is deliberately **not** the wire order — `setPosition` is presented as
position, mode, index but encoded as `index,mode,position`. `csv` encoding joins
by `ParamField` declaration order in the `CommandDef`, which is the wire order;
the emitted YAML orders fields independently for readability.

**Names and descriptions are written inline in `services.yaml`, not into
`translations/en.json`.** Home Assistant re-reads `services.yaml` when the set of
registered services changes, but does not re-read a custom integration's
translations, so translation-based labels would not appear until a restart.

**The file is produced with `yaml.safe_dump`, not f-string templating.** The
current `_write_services_yaml()` interpolates device labels directly
(`services.py:128`), so a device named `Bob's "TV"` already produces malformed
YAML today. User-supplied IR button names will also reach this file, which makes
correct quoting mandatory.

### Devices that generate nothing

Hubs, meters, sensors, cameras and `Remote` produce no actions. This is already
encoded by the `_hub` and `_no_commands` entries in `DEVICE_TYPE_ALIASES`. For
the reference account that is 6 of 13 devices.

### Unknown device types

A physical device whose type is absent from the index still gets a device action
with a free-text `command` field and a `parameter` text field, its description
pointing at `send_command`. A newly released SwitchBot device is never dead.

## Infrared remotes

IR commands split into two classes, and only one is indexable.

| Class | `commandType` | Source | Indexable |
| --- | --- | --- | --- |
| Standard | `command` | Fixed per `remoteType` by the API: `turnOn`/`turnOff` for every type except `Others`, plus `setAll` (Air Conditioner), `SetChannel`/`volumeAdd`/`volumeSub`/`channelAdd`/`channelSub` (TV, IPTV/Streamer, Set Top Box), `setMute`/`Play`/`Pause`/`Stop`/`FastForward`/`Rewind`/`Next`/`Previous` (DVD, Speaker), `swing`/`timer`/`lowSpeed`/`middleSpeed`/`highSpeed` (Fan), `brightnessUp`/`brightnessDown` (Light) | Yes |
| Custom buttons | `customize` | The button name as typed in the SwitchBot app; upstream's own example is `"command": "ボタン"` | No |

### Command type resolution

This replaces the `device_type == "Others"` test at `services.py:243-244`:

```
IR device, chosen command:
  matches a registered or learned custom button name  -> customize
  matches a standard command for this remoteType      -> command
  remoteType is Others (no standard commands exist)   -> customize
```

Upstream states: "For infrared remote devices, when you have created customized
buttons, you must set `commandType` to `customize`." That applies to **any**
remote type, not only `Others`. The current code sets `customize` only for
`Others`, so a custom button on a TV-type remote is sent with
`commandType: command` and silently fails. This is a live bug fixed by the
resolution order above.

### Presentation

A typed remote gets one dropdown containing its standard commands from the index
followed by its registered custom buttons, marked as such — `Volume up`,
`Next channel`, `Bright (custom button)`. Home Assistant's `select` selector does
not support option groups, so the two sets are concatenated rather than
separated.

The selector is generated with `custom_value: true`, rendering a combo box, so a
brand-new button name can still be typed inline without visiting Configure.

### Storage and collection

Names live in `entry.options["ir_buttons"][device_id]` as a list of strings.
They are stored and matched **verbatim** — upstream documents custom button names
as case-sensitive — and are never slugged, because they only ever appear as
dropdown *values*, never as action names.

`config_flow.py` changes:

- `async_step_init` becomes a menu: *Device list* (today's read-only summary,
  unchanged) and *Custom IR buttons*.
- *Custom IR buttons* -> select an IR remote -> a multi-line text field
  pre-filled with the current names, one per line.
- On save, call the regeneration path directly rather than relying on a reload.

`OptionsFlow.async_create_entry(data=...)` **replaces** the entire options dict,
so the handler must merge; otherwise it would erase `service_aliases`.

### Auto-remembering

In the shared `_async_send()`, a command sent with `commandType: customize` that
returns `statusCode: 100` has its name appended to that device's list if not
already present, followed by regeneration. This runs only when the name is new,
so ordinary sends do no extra work. There is no update listener on the config
entry today, so writing options does not trigger a reload loop; regeneration is
invoked explicitly.

### Unverified: DIY remote types

SwitchBot is reported to return `remoteType` values such as `DIY TV` and
`DIY Air Conditioner` for DIY-learned remotes. This is **not** documented in the
API repository and could not be confirmed. Handling is defensive: strip a
leading `DIY ` when resolving standard commands, and fall back to
customize-only for any unrecognized `remoteType`. The reference account has only
plain `Others` remotes, so this path will not appear in the maintainer's smoke
test.

## Runtime flow

`async_refresh_device_cache()` becomes:

1. Fetch devices (unchanged).
2. Build the generated-service set from devices x merged index x
   `entry.options["ir_buttons"]`.
3. Write `services.yaml` **through `hass.async_add_executor_job`**. The current
   implementation calls `Path.write_text()` synchronously inside an async
   function (`services.py:166`), which current Home Assistant flags as a
   blocking call in the event loop.
4. Remove generated services that are no longer valid.
5. Register the current set.

Triggered on config entry setup, on the *Refresh device list* button
(`button.py:61`), on the `get_devices` service call, and after an options-flow
save. Setup regenerates unconditionally, because HACS overwrites the installed
integration directory on update and takes the generated `services.yaml` with it.

Each generated service is registered with a closure that resolves the device ID
via the alias map, looks up the `CommandDef`, encodes `parameter` from
`call.data` according to `encoding`, and sends. The POST body of
`async_send_command` (`services.py:301-351`) is extracted into a shared
`_async_send(hass, entry, device, command, parameter, command_type)` used by both
the generated actions and the untouched `send_command`.

## Bugs fixed along the way

These exist today, independent of this feature:

1. **Blocking I/O in the event loop** — `_write_services_yaml()` calls
   `Path.write_text()` from async context (`services.py:166`).
2. **Unsafe YAML construction** — device labels are f-string interpolated into
   `services.yaml` (`services.py:128`); quotes or colons in a device name
   produce malformed YAML.
3. **`customize` restricted to `Others`** — custom buttons on typed IR remotes
   are sent with the wrong `commandType` (`services.py:243-244`).
4. **Air Conditioner mode `0`** — undocumented in the current index; upstream
   documents `0/1 (auto)`.

## Testing

`tests/`, pytest, no Home Assistant required:

| File | Covers |
| --- | --- |
| `test_doc_parser.py` | Table extraction from checked-in fixture markdown; blank-leading-cell carry-forward; device-type reconciliation failing loudly |
| `test_schema_derivation.py` | Ranges -> `number`; positional specs -> `csv` fields; enumerations -> `select` options; JSON bodies -> `json` fields; unparseable -> `text` with help |
| `test_parameter_encoding.py` | `position 80` + default mode -> `"0,ff,80"`; `26`/cool/medium/on -> `"26,2,3,on"`; JSON object assembly; `none` passthrough |
| `test_service_naming.py` | Slugging; collision suffixes; alias map across a rename; dropping slugs whose device is gone |
| `test_ir_commands.py` | Command-type resolution across all three cases; learned-button dedupe; case-sensitive matching |
| `test_yaml_safety.py` | Names containing quotes, colons and non-ASCII (`ボタン`) round-trip correctly |
| `test_options_merge.py` | Options-flow save preserves `service_aliases` |

Fixtures are real upstream markdown files checked into `tests/fixtures/`, so
parser tests do not require network access.

The maintainer then installs the result and confirms the action picker renders
the generated actions, dropdowns and sliders as intended.

## Risks and unknowns

**Whether new actions appear without a Home Assistant restart.** Home Assistant
caches service descriptions; the expectation is that it re-reads `services.yaml`
when it encounters registered services it has no description for, but this is
not confirmed. It is verified with a cheap probe *before* building on it. If a
restart turns out to be required, the fallback is a persistent notification
after a device-list change telling the user to restart — not a redesign.

**Upstream markdown formatting is the generator's contract.** If SwitchBot
restructures the docs, the generator fails at build time with a clear error.
Runtime is unaffected, because the generated module is committed.

**Action-list growth.** ~11 actions for a 13-device account. A 40-device account
would see proportionally more. Acceptable given the action picker is searchable;
revisit if it becomes a complaint.

## File inventory

| File | Change |
| --- | --- |
| `tools/generate_command_index.py` | New — build-time generator |
| `tests/fixtures/*.md` | New — upstream markdown fixtures |
| `command_index.py` | New — generated, committed |
| `command_overlay.py` | New — hand-written labels and fallback schemas |
| `device_commands.py` | Rewritten — `ParamField`/`CommandDef`, merge, lookup API; `get_commands_for_device_type` signature preserved |
| `service_generator.py` | New — naming, alias map, `services.yaml` emission, handler registration |
| `services.py` | Extract `_async_send`; executor-based YAML write; `yaml.safe_dump`; call the generator; IR command-type fix; auto-remember |
| `config_flow.py` | Options flow becomes a menu; custom IR button step; merging save |
| `__init__.py` | Regenerate unconditionally on setup |
| `button.py` | Refresh triggers regeneration (existing call path) |
| `README.md` | Document generated actions, IR button registration, `send_command` as escape hatch |
| `manifest.json` | 4.0.0 |

## Build order

The work is sequenced so each stage is independently verifiable and the risky
unknown is settled before anything depends on it.

1. **Probe the restart question** (see Risks). Throwaway: register a service and
   a `services.yaml` entry at runtime, confirm whether the picker shows it
   without a restart. Settles a design assumption for the cost of minutes.
2. **Generator + parser, with tests.** Produces `command_index.py`. Reviewable as
   a pure data diff, no integration changes yet.
3. **Data model + overlay.** Rewrite `device_commands.py` around `ParamField` /
   `CommandDef`, seed `command_overlay.py` from the existing prose, keep
   `get_commands_for_device_type` working so nothing regresses.
4. **`service_generator.py`**: naming, alias map, `yaml.safe_dump` emission.
   Tested without Home Assistant by asserting on emitted YAML.
5. **Wire into runtime**: extract `_async_send`, executor-based write,
   registration and teardown. First point at which the feature is usable.
6. **IR handling**: command-type fix, options-flow menu and button step,
   auto-remembering.
7. **README and version bump.**

Stages 1-4 touch no runtime behaviour, so the integration stays working
throughout; stage 5 is the first one that needs a smoke test.

## Release

Version 4.0.0. No breaking changes to existing behaviour — the major bump
reflects the new action surface, not a migration. `send_command` continues to
work exactly as before.
