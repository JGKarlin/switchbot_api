from __future__ import annotations

from conftest import load_integration_module

ci = load_integration_module("command_index")


def test_smart_lock_alias_resolves_to_a_real_command_index_entry():
    assert "Smart Lock" in ci.GENERATED_TYPE_ALIASES
    target = ci.GENERATED_TYPE_ALIASES["Smart Lock"]
    assert target in ci.COMMAND_INDEX


def test_every_alias_value_points_at_a_real_index_entry():
    for declared, target in ci.GENERATED_TYPE_ALIASES.items():
        assert target in ci.COMMAND_INDEX or target in ci.IR_COMMAND_INDEX, (
            f"{declared!r} -> {target!r} does not point at a real device type"
        )


def test_no_alias_key_shadows_a_real_command_index_entry():
    overlap = set(ci.GENERATED_TYPE_ALIASES) & set(ci.COMMAND_INDEX)
    assert not overlap, f"alias keys must not duplicate real index keys: {overlap}"


def test_sanity_anchors_for_real_owned_devices():
    assert "Curtain" in ci.COMMAND_INDEX
    assert "Plug Mini (JP)" in ci.COMMAND_INDEX
    assert "Air Conditioner" in ci.IR_COMMAND_INDEX
    assert "TV" in ci.IR_COMMAND_INDEX
    assert "Others" not in ci.IR_COMMAND_INDEX
