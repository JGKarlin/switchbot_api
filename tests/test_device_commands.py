from __future__ import annotations

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


# --- Generated-alias resolution order (command_index.GENERATED_TYPE_ALIASES) ---
#
# command_index.py exports GENERATED_TYPE_ALIASES: it maps the deviceType
# spelling the SwitchBot API actually returns (e.g. "Smart Lock") to the
# spelling used in the docs' command table (e.g. "Lock"). Resolution order
# must be: hand-written DEVICE_TYPE_ALIASES first, then GENERATED_TYPE_ALIASES,
# then the device type as a direct key.


def test_smart_lock_generated_alias_resolves_to_same_commands_as_lock():
    """Headline regression guard: the repo owner's own front door lock reports
    deviceType "Smart Lock", which upstream's docs index under "Lock". Without
    consulting GENERATED_TYPE_ALIASES this device resolves to zero commands.
    """
    smart_lock = dc.get_commands_for_device_type("Smart Lock")
    lock = dc.get_commands_for_device_type("Lock")
    assert smart_lock != []
    assert smart_lock == lock


def test_overlay_reaches_aliased_device_through_the_resolved_type():
    """Exercises the generated-alias hop AND the overlay in one assertion.

    Fails if either the alias resolution or the overlay merge is removed:
    without the alias, Curtain3 resolves to nothing; without the overlay,
    the label is the generated "Turn on".
    """
    cmd = dc.find_command("Curtain3", "turnOn")
    assert cmd is not None
    assert cmd.label == "Open curtain"


def test_smart_lock_keeps_working_through_the_alias_without_an_overlay_entry():
    """"Smart Lock" resolves to "Lock" via GENERATED_TYPE_ALIASES with no
    COMMAND_OVERLAY entry involved -- the generated label "Lock" is already
    correct, so no overlay patch is needed here. This only proves the alias
    hop keeps working, not the overlay merge (see the test above for that).
    """
    cmd = dc.find_command("Smart Lock", "lock")
    assert cmd is not None
    assert cmd.label == "Lock"


def test_curtain3_generated_alias_resolves_to_same_commands_as_curtain_3():
    assert dc.get_commands_for_device_type(
        "Curtain3"
    ) == dc.get_commands_for_device_type("Curtain 3")


def test_hand_written_alias_wins_over_generated_alias():
    """DEVICE_TYPE_ALIASES must be consulted before GENERATED_TYPE_ALIASES.

    "Smart Lock" is not itself a hand-written alias today, but if it were, it
    must win over the generated alias (which redirects it to "Lock"). Prove
    the resolution order by temporarily adding a conflicting hand-written
    entry and confirming it takes precedence.
    """
    assert "Smart Lock" not in dc.DEVICE_TYPE_ALIASES
    assert "Smart Lock" in dc.GENERATED_TYPE_ALIASES
    dc.DEVICE_TYPE_ALIASES["Smart Lock"] = "_no_commands"
    try:
        assert dc.get_commands_for_device_type("Smart Lock") == []
    finally:
        del dc.DEVICE_TYPE_ALIASES["Smart Lock"]
