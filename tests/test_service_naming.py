from __future__ import annotations

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
