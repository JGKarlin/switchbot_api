from __future__ import annotations

from conftest import load_integration_module, load_tool_module

dc = load_integration_module("device_commands")


def test_typed_remote_standard_command_uses_command_type():
    assert dc.resolve_command_type("TV", "volumeAdd", is_infrared=True) == "command"


def test_typed_remote_custom_button_uses_customize():
    """Regression: custom buttons on typed remotes were sent as commandType=command."""
    assert (
        dc.resolve_command_type(
            "TV", "Netflix", is_infrared=True, custom_buttons=("Netflix",)
        )
        == "customize"
    )


def test_others_remote_always_uses_customize():
    assert dc.resolve_command_type("Others", "Bright", is_infrared=True) == "customize"


def test_others_remote_uses_customize_even_for_command_like_names():
    assert dc.resolve_command_type("Others", "turnOn", is_infrared=True) == "customize"


def test_custom_button_matching_is_case_sensitive():
    """Upstream documents custom button names as case-sensitive."""
    assert (
        dc.resolve_command_type(
            "TV", "netflix", is_infrared=True, custom_buttons=("Netflix",)
        )
        == "command"
    )


def test_unknown_ir_remote_type_falls_back_to_customize():
    assert (
        dc.resolve_command_type("Espresso Machine", "Brew", is_infrared=True)
        == "customize"
    )


def test_diy_prefix_is_stripped_when_resolving_standard_commands():
    assert dc.get_commands_for_device_type("DIY TV", is_infrared=True) == (
        dc.get_commands_for_device_type("TV", is_infrared=True)
    )


def test_physical_device_is_unaffected():
    assert dc.resolve_command_type("Bot", "turnOn") == "command"


def test_typed_remote_has_turn_on_from_the_all_types_row():
    commands = [c.command for c in dc.get_commands_for_device_type("TV", is_infrared=True)]
    assert "turnOn" in commands
    assert "volumeAdd" in commands


def test_others_remote_has_no_standard_commands():
    assert dc.get_commands_for_device_type("Others", is_infrared=True) == []


def test_all_ir_except_others_matches_doc_parser():
    """The same constant is defined independently in the build-time parser and
    the runtime module. If they ever drift, infrared devices silently lose
    their standard commands.
    """
    doc_parser = load_tool_module("doc_parser")
    assert doc_parser.ALL_IR_EXCEPT_OTHERS == dc.ALL_IR_EXCEPT_OTHERS
