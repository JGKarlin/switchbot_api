from __future__ import annotations

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
