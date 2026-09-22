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
    assert {c.command for c in dropdown.commands} == {"turnOn", "turnOff", "pause"}
    # setPosition takes input, so it gets its own action instead
    assert "setPosition" not in {c.command for c in dropdown.commands}


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
    assert aliases["office_curtain"]["device_id"] == "E1"
    assert aliases["office_curtain"]["command"] is None
    assert aliases["office_curtain_move_to_position"]["device_id"] == "E1"
    assert aliases["office_curtain_move_to_position"]["command"] == "setPosition"


def test_rename_keeps_the_old_slug_alive():
    """A renamed device must not break automations using the old action."""
    existing = {
        "office_curtain": {"device_id": "E1", "command": None},
        "office_curtain_move_to_position": {"device_id": "E1", "command": "setPosition"},
    }
    services, aliases = sg.build_services(
        [device("Study Curtain", "Curtain", "E1")], existing_aliases=existing
    )
    names = [s.name for s in services]
    assert "study_curtain" in names
    assert "office_curtain" in names
    assert aliases["office_curtain"]["device_id"] == "E1"
    assert aliases["study_curtain"]["device_id"] == "E1"


def test_rename_keeps_the_historical_parameterized_slug_as_parameterized():
    """The restored slug must come back as the parameterized action, not the dropdown.

    Regression test: filtering the restore lookup on command_def is None alone
    would rebuild every historical slug from the dropdown action, silently
    stripping the fields an automation's `position: 80` call depends on.
    """
    existing = {
        "office_curtain": {"device_id": "E1", "command": None},
        "office_curtain_move_to_position": {"device_id": "E1", "command": "setPosition"},
    }
    services, aliases = sg.build_services(
        [device("Study Curtain", "Curtain", "E1")], existing_aliases=existing
    )
    restored = next(s for s in services if s.name == "office_curtain_move_to_position")
    assert restored.command_def is not None
    assert restored.command_def.command == "setPosition"
    assert restored.command_def.fields
    assert aliases["office_curtain_move_to_position"] == {
        "device_id": "E1",
        "command": "setPosition",
    }


def test_rename_keeps_the_historical_dropdown_slug_as_dropdown():
    existing = {
        "office_curtain": {"device_id": "E1", "command": None},
        "office_curtain_move_to_position": {"device_id": "E1", "command": "setPosition"},
    }
    services, aliases = sg.build_services(
        [device("Study Curtain", "Curtain", "E1")], existing_aliases=existing
    )
    restored = next(s for s in services if s.name == "office_curtain")
    assert restored.command_def is None
    assert {c.command for c in restored.commands} == {"turnOn", "turnOff", "pause"}
    assert aliases["office_curtain"] == {"device_id": "E1", "command": None}


def test_historical_slug_claimed_by_a_different_device_is_dropped():
    """Restoring a stale slug must never redirect an automation to another device."""
    existing = {"curtain": {"device_id": "E1", "command": None}}
    services, aliases = sg.build_services(
        [
            device("Study Curtain", "Curtain", "E1"),
            device("Curtain", "Curtain", "E2"),
        ],
        existing_aliases=existing,
    )
    assert aliases["curtain"] == {"device_id": "E2", "command": None}
    names = [s.name for s in services]
    assert names.count("curtain") == 1
    curtain_service = next(s for s in services if s.name == "curtain")
    assert curtain_service.device_id == "E2"


def test_historical_alias_for_a_removed_command_is_dropped():
    """If the recorded command no longer exists for the device, drop the alias."""
    existing = {
        "office_curtain_old_feature": {"device_id": "E1", "command": "discontinuedCommand"},
    }
    services, aliases = sg.build_services(
        [device("Office Curtain", "Curtain", "E1")], existing_aliases=existing
    )
    assert "office_curtain_old_feature" not in aliases
    assert "office_curtain_old_feature" not in [s.name for s in services]


def test_alias_for_a_removed_device_is_dropped():
    existing = {"old_gadget": {"device_id": "GONE1", "command": None}}
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
    assert labels["volumeAdd"] == "Volume add"


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


def test_device_named_send_command_does_not_claim_the_reserved_slug():
    """A device slugifying to a built-in action name must be renamed, not
    allowed to collide -- otherwise merging generated and static services
    would silently overwrite send_command's five-field schema."""
    services, _ = sg.build_services(
        [device("Send Command", "Curtain", "E1")]
    )
    dropdown = next(s for s in services if s.command_def is None)
    assert dropdown.name != "send_command"
    assert dropdown.name.startswith("send_command_")


def test_send_command_block_survives_a_colliding_device_name():
    """Rendering must still produce the real send_command action with all
    five of its fields intact, unshadowed by the renamed device action."""
    services, _ = sg.build_services([device("Send Command", "Curtain", "E1")])
    text = sg.render_services_yaml(services, device_labels=[])
    import yaml as _yaml

    data = _yaml.safe_load(text)
    assert set(data["send_command"]["fields"]) == {
        "device_name", "device_id", "command", "parameter", "command_type"
    }


def test_device_named_get_devices_does_not_claim_the_reserved_slug():
    services, _ = sg.build_services(
        [device("Get Devices", "Curtain", "E2")]
    )
    dropdown = next(s for s in services if s.command_def is None)
    assert dropdown.name != "get_devices"
    assert dropdown.name.startswith("get_devices_")
