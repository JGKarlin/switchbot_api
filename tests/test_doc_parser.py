from __future__ import annotations

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


def test_raises_on_embedded_pipe_in_cell():
    """A row with a literal pipe in a cell is malformed and must be rejected."""
    markdown = """## Control Commands

| deviceType | commandType | command | parameterSpec | description |
|---|---|---|---|---|
| Device | command | myCmd | default | use `a|b` syntax |
"""
    with pytest.raises(dp.MalformedCommandRow) as exc:
        dp.parse_control_commands(markdown)
    assert "6 cells" in str(exc.value)


def test_all_fixtures_parse_without_malformed_row_error():
    """Regression guard: ensure no legitimate upstream content is rejected."""
    fixture_names = ["curtain-3.md", "evaporative-humidifier.md",
                     "virtual-infrared-remote-devices.md", "plug-mini-jp.md", "bot.md"]
    for name in fixture_names:
        rows = dp.parse_control_commands(fixture(name))
        assert isinstance(rows, list)
