from __future__ import annotations

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


def test_json_int_coercion_error_raises_parameter_error():
    cmd = ct.CommandDef(
        command="setThing",
        encoding="json",
        fields=(ct.ParamField(key="count", label="Count", value_type="int"),),
    )
    with pytest.raises(ct.ParameterError) as exc:
        ct.encode_parameter(cmd, {"count": "not_a_number"})
    assert "Count" in str(exc.value)
