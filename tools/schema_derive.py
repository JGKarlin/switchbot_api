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
_PAREN_ENUM_RE = re.compile(r"([A-Za-z0-9/]+)\s*\(([A-Za-z][A-Za-z /-]*)\)")
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
