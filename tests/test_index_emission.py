from __future__ import annotations

from conftest import load_integration_module, load_tool_module

gen = load_tool_module("generate_command_index")
ct = load_integration_module("command_types")


def test_rendered_module_is_valid_python_and_round_trips():
    physical = {
        "Bot": [
            ct.CommandDef(command="turnOn", label="Turn on", encoding="none"),
            ct.CommandDef(
                command="setPosition",
                label="Move to position",
                encoding="csv",
                parameter="",
                fields=(
                    ct.ParamField(key="position", label="Position", kind="number",
                                  minimum=0, maximum=100),
                ),
            ),
        ]
    }
    infrared = {
        "TV": [ct.CommandDef(command="volumeAdd", label="Volume up")],
    }

    source = gen.render_index_module(physical, infrared)

    namespace = {"CommandDef": ct.CommandDef, "ParamField": ct.ParamField}
    exec(compile(source.replace("from .command_types import", "# from"),
                 "<generated>", "exec"), namespace)

    assert namespace["COMMAND_INDEX"]["Bot"][0].command == "turnOn"
    assert namespace["COMMAND_INDEX"]["Bot"][1].fields[0].maximum == 100
    assert namespace["IR_COMMAND_INDEX"]["TV"][0].label == "Volume up"


def test_rendered_module_declares_its_relative_import():
    source = gen.render_index_module({}, {})
    assert "from .command_types import CommandDef, ParamField" in source


def test_rendered_module_warns_against_hand_editing():
    source = gen.render_index_module({}, {})
    assert "generated" in source.lower()
