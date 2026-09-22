from conftest import load_integration_module


def test_loader_imports_existing_device_commands():
    mod = load_integration_module("device_commands")
    commands = [c.command for c in mod.get_commands_for_device_type("Bot")]
    assert "turnOn" in commands
    assert "press" in commands


def test_loader_does_not_import_homeassistant():
    import sys

    load_integration_module("device_commands")
    assert "homeassistant" not in sys.modules
