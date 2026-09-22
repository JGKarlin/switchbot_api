from __future__ import annotations

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


def test_position_range_survives_narrower_window():
    """Regression guard: position must still resolve its 0~100 range once
    _describe_window stops at the next sibling key instead of a fixed
    character count (position is the last field, so its window should run
    to the end of the description)."""
    cmd = sd.derive_command(
        row(
            "setPosition",
            "index0,mode0,position0 e.g. 0,ff,80",
            "mode: 0 (Performance Mode), 1 (Silent Mode), ff (default mode) "
            "position: 0~100 (0 means open, 100 means closed)",
        )
    )
    position = next(f for f in cmd.fields if f.key == "position")
    assert (position.minimum, position.maximum) == (0, 100)


def test_index_field_does_not_inherit_a_sibling_key_s_options():
    """`index` is never mentioned in the description at all. A window that
    falls back to the whole text (instead of an empty window) would hand
    it `mode`'s Performance Mode / Silent Mode / Default mode options."""
    cmd = sd.derive_command(
        row(
            "setPosition",
            "index0,mode0,position0 e.g. 0,ff,80",
            "mode: 0 (Performance Mode), 1 (Silent Mode), ff (default mode) "
            "position: 0~100 (0 means open, 100 means closed)",
        )
    )
    index = next(f for f in cmd.fields if f.key == "index")
    assert index.options == ()
    assert index.kind != "select"


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


def test_air_conditioner_temperature_is_a_plain_number():
    """`temperature` is documented ("the unit of temperature is in
    celsius") but a fixed-width window overruns into the `mode` clause and
    turns temperature into a dropdown of mode values instead of a Celsius
    number field -- which would send the wrong value to real hardware."""
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
    temperature = next(f for f in cmd.fields if f.key == "temperature")
    assert temperature.kind == "number"
    assert temperature.options == ()
    assert temperature.default == "26"


def test_air_conditioner_mode_options_survive_narrower_window():
    """Regression guard: narrowing the window to stop at the next sibling
    key (here, fan_speed) must not break the case that already worked --
    mode must still resolve exactly its five documented options."""
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
    mode = next(f for f in cmd.fields if f.key == "mode")
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


def test_humidifier_mode_options_include_the_first_comma_led_entry():
    """`_BACKTICK_ENUM_RE` required a semicolon or string-start before a
    `value, label` pair. The first pair in `mode_int, 1, level 4; 2, level
    3; ...` is preceded by a comma, not a semicolon, so option "1" ("Level
    4") was dropped and unreachable in the generated UI."""
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
    mode = next(f for f in cmd.fields if f.key == "mode")
    options = dict(mode.options)
    assert options["1"] == "Level 4"
    assert options["8"] == "Drying mode"


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
