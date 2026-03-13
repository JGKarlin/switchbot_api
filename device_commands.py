"""SwitchBot API device command definitions.

Comprehensive command map derived from the SwitchBot API v1.1 specification:
https://github.com/OpenWonderLabs/SwitchBotAPI
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandDef:
    """A single command supported by a device type."""

    command: str
    command_type: str = "command"
    parameter: str = "default"
    parameter_description: str = ""
    parameter_options: list[str] = field(default_factory=list)
    requires_user_input: bool = False


PHYSICAL_DEVICE_COMMANDS: dict[str, list[CommandDef]] = {
    "Bot": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("press", parameter_description="Trigger press"),
    ],
    "Curtain": [
        CommandDef("turnOn", parameter_description="Open curtain (position 0)"),
        CommandDef("turnOff", parameter_description="Close curtain (position 100)"),
        CommandDef("pause", parameter_description="Pause movement"),
        CommandDef(
            "setPosition",
            parameter="",
            parameter_description="index,mode,position (e.g. 0,ff,80). mode: 0=Performance, 1=Silent, ff=default. position: 0=open, 100=closed",
            requires_user_input=True,
        ),
    ],
    "Curtain 3": [
        CommandDef("turnOn", parameter_description="Open curtain (position 0)"),
        CommandDef("turnOff", parameter_description="Close curtain (position 100)"),
        CommandDef("pause", parameter_description="Pause movement"),
        CommandDef(
            "setPosition",
            parameter="",
            parameter_description="index,mode,position (e.g. 0,ff,80). mode: 0=Performance, 1=Silent, ff=default. position: 0=open, 100=closed",
            requires_user_input=True,
        ),
    ],
    "Smart Lock": [
        CommandDef("lock", parameter_description="Rotate to locked position"),
        CommandDef("unlock", parameter_description="Rotate to unlocked position"),
    ],
    "Lock": [
        CommandDef("lock", parameter_description="Rotate to locked position"),
        CommandDef("unlock", parameter_description="Rotate to unlocked position"),
        CommandDef("deadbolt", parameter_description="Disengage deadbolt or latch"),
    ],
    "Lock Pro": [
        CommandDef("lock", parameter_description="Rotate to locked position"),
        CommandDef("unlock", parameter_description="Rotate to unlocked position"),
        CommandDef("deadbolt", parameter_description="Disengage deadbolt or latch"),
    ],
    "Lock Ultra": [
        CommandDef("lock", parameter_description="Rotate to locked position"),
        CommandDef("unlock", parameter_description="Rotate to unlocked position"),
        CommandDef("deadbolt", parameter_description="Disengage deadbolt or latch"),
    ],
    "Lock Lite": [
        CommandDef("lock", parameter_description="Rotate to locked position"),
        CommandDef("unlock", parameter_description="Rotate to unlocked position"),
    ],
    "Humidifier": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description="auto, 101 (34%), 102 (67%), 103 (100%), or 0-100 for custom %",
            parameter_options=["auto", "101", "102", "103"],
            requires_user_input=True,
        ),
    ],
    "Humidifier2": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description='JSON: {"mode": int, "targetHumidify": int}. mode: 1=Level4, 2=Level3, 3=Level2, 4=Level1, 5=Humidity, 6=Sleep, 7=Auto, 8=Drying. targetHumidify: 0-100',
            requires_user_input=True,
        ),
        CommandDef(
            "setChildLock",
            parameter="",
            parameter_description="Enable or disable child lock",
            parameter_options=["true", "false"],
        ),
    ],
    "Air Purifier VOC": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description='JSON: {"mode": int, "fanGear": int}. mode: 1=Normal/Fan, 2=Auto, 3=Sleep, 4=Pet. fanGear: 1-3 (only for mode 1)',
            requires_user_input=True,
        ),
        CommandDef(
            "setChildLock",
            parameter="",
            parameter_description="Enable or disable child lock",
            parameter_options=["0", "1"],
        ),
    ],
    "Air Purifier Table VOC": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description='JSON: {"mode": int, "fanGear": int}. mode: 1=Normal/Fan, 2=Auto, 3=Sleep, 4=Pet. fanGear: 1-3 (only for mode 1)',
            requires_user_input=True,
        ),
        CommandDef(
            "setChildLock",
            parameter="",
            parameter_description="Enable or disable child lock",
            parameter_options=["0", "1"],
        ),
    ],
    "Air Purifier PM2.5": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description='JSON: {"mode": int, "fanGear": int}. mode: 1=Normal/Fan, 2=Auto, 3=Sleep, 4=Pet. fanGear: 1-3 (only for mode 1)',
            requires_user_input=True,
        ),
        CommandDef(
            "setChildLock",
            parameter="",
            parameter_description="Enable or disable child lock",
            parameter_options=["0", "1"],
        ),
    ],
    "Air Purifier Table PM2.5": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description='JSON: {"mode": int, "fanGear": int}. mode: 1=Normal/Fan, 2=Auto, 3=Sleep, 4=Pet. fanGear: 1-3 (only for mode 1)',
            requires_user_input=True,
        ),
        CommandDef(
            "setChildLock",
            parameter="",
            parameter_description="Enable or disable child lock",
            parameter_options=["0", "1"],
        ),
    ],
    "Plug": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
    ],
    "Plug Mini (US)": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
    ],
    "Plug Mini (JP)": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
    ],
    "Plug Mini (EU)": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
    ],
    "Color Bulb": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
    ],
    "Strip Light": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
    ],
    "Strip Light 3": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
    ],
    "Robot Vacuum Cleaner S1": [
        CommandDef("start", parameter_description="Start vacuuming"),
        CommandDef("stop", parameter_description="Stop vacuuming"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "PowLevel",
            parameter="",
            parameter_description="Suction power level",
            parameter_options=["0", "1", "2", "3"],
        ),
    ],
    "Robot Vacuum Cleaner S1 Plus": [
        CommandDef("start", parameter_description="Start vacuuming"),
        CommandDef("stop", parameter_description="Stop vacuuming"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "PowLevel",
            parameter="",
            parameter_description="Suction power level",
            parameter_options=["0", "1", "2", "3"],
        ),
    ],
    "K10+": [
        CommandDef("start", parameter_description="Start vacuuming"),
        CommandDef("stop", parameter_description="Stop vacuuming"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "PowLevel",
            parameter="",
            parameter_description="Suction power level",
            parameter_options=["0", "1", "2", "3"],
        ),
    ],
    "K10+ Pro": [
        CommandDef("start", parameter_description="Start vacuuming"),
        CommandDef("stop", parameter_description="Stop vacuuming"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "PowLevel",
            parameter="",
            parameter_description="Suction power level",
            parameter_options=["0", "1", "2", "3"],
        ),
    ],
    "K20+ Pro": [
        CommandDef(
            "startClean",
            parameter="",
            parameter_description='JSON: {"action": "sweep"|"mop", "param": {"fanLevel": 1-4, "times": 1-N}}',
            requires_user_input=True,
        ),
        CommandDef("pause", parameter_description="Pause cleaning"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "setVolume",
            parameter="",
            parameter_description="Volume level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "changeParam",
            parameter="",
            parameter_description='JSON: {"fanLevel": 1-4, "waterLevel": 1-2, "times": 1-N}',
            requires_user_input=True,
        ),
    ],
    "Robot Vacuum Cleaner K10+ Pro Combo": [
        CommandDef(
            "startClean",
            parameter="",
            parameter_description='JSON: {"action": "sweep"|"mop", "param": {"fanLevel": 1-4, "times": 1-N}}',
            requires_user_input=True,
        ),
        CommandDef("pause", parameter_description="Pause cleaning"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "setVolume",
            parameter="",
            parameter_description="Volume level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "changeParam",
            parameter="",
            parameter_description='JSON: {"fanLevel": 1-4, "times": 1-N}',
            requires_user_input=True,
        ),
    ],
    "Floor Cleaning Robot S10": [
        CommandDef(
            "startClean",
            parameter="",
            parameter_description='JSON: {"action": "sweep"|"sweep_mop", "param": {"fanLevel": 1-4, "waterLevel": 1-2, "times": 1-N}}',
            requires_user_input=True,
        ),
        CommandDef("addWaterForHumi", parameter_description="Refill evaporative humidifier"),
        CommandDef("pause", parameter_description="Pause cleaning"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "setVolume",
            parameter="",
            parameter_description="Volume level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "selfClean",
            parameter="",
            parameter_description="Self-clean mode",
            parameter_options=["1", "2", "3"],
        ),
        CommandDef(
            "changeParam",
            parameter="",
            parameter_description='JSON: {"fanLevel": 1-4, "waterLevel": 1-2, "times": 1-N}',
            requires_user_input=True,
        ),
    ],
    "S20": [
        CommandDef(
            "startClean",
            parameter="",
            parameter_description='JSON: {"action": "sweep"|"sweep_mop", "param": {"fanLevel": 1-4, "waterLevel": 1-2, "times": 1-N}}',
            requires_user_input=True,
        ),
        CommandDef("addWaterForHumi", parameter_description="Refill evaporative humidifier"),
        CommandDef("pause", parameter_description="Pause cleaning"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "setVolume",
            parameter="",
            parameter_description="Volume level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "selfClean",
            parameter="",
            parameter_description="Self-clean mode",
            parameter_options=["1", "2", "3"],
        ),
        CommandDef(
            "changeParam",
            parameter="",
            parameter_description='JSON: {"fanLevel": 1-4, "waterLevel": 1-2, "times": 1-N}',
            requires_user_input=True,
        ),
    ],
    "K11+": [
        CommandDef(
            "startClean",
            parameter="",
            parameter_description='JSON: {"action": "sweep"|"mop", "param": {"fanLevel": 1-4, "times": 1-N}}',
            requires_user_input=True,
        ),
        CommandDef("pause", parameter_description="Pause cleaning"),
        CommandDef("dock", parameter_description="Return to charging dock"),
        CommandDef(
            "setVolume",
            parameter="",
            parameter_description="Volume level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "changeParam",
            parameter="",
            parameter_description='JSON: {"fanLevel": 1-4, "waterLevel": 1-2, "times": 1-N}',
            requires_user_input=True,
        ),
    ],
    "Ceiling Light": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
    ],
    "Ceiling Light Pro": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
    ],
    "RGBICWW Strip Light": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
    ],
    "RGBICWW Floor Lamp": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
    ],
    "RGBIC Neon Wire Rope Light": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
    ],
    "RGBIC Neon Rope Light": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
    ],
    "Smart Radiator Thermostat": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description="Thermostat mode",
            parameter_options=["0", "1", "2", "3", "4", "5"],
        ),
        CommandDef(
            "setManualModeTemperature",
            parameter="",
            parameter_description="Temperature 4-35 °C",
            requires_user_input=True,
        ),
    ],
    "Keypad": [
        CommandDef(
            "createKey",
            parameter="",
            parameter_description='JSON: {"name": str, "type": "permanent"|"timeLimit"|"disposable"|"urgent", "password": str (6-12 digits), "startTime": timestamp, "endTime": timestamp}',
            requires_user_input=True,
        ),
        CommandDef(
            "deleteKey",
            parameter="",
            parameter_description='JSON: {"id": passcode_id}',
            requires_user_input=True,
        ),
    ],
    "Keypad Touch": [
        CommandDef(
            "createKey",
            parameter="",
            parameter_description='JSON: {"name": str, "type": "permanent"|"timeLimit"|"disposable"|"urgent", "password": str (6-12 digits), "startTime": timestamp, "endTime": timestamp}',
            requires_user_input=True,
        ),
        CommandDef(
            "deleteKey",
            parameter="",
            parameter_description='JSON: {"id": passcode_id}',
            requires_user_input=True,
        ),
    ],
    "Keypad Vision": [
        CommandDef(
            "createKey",
            parameter="",
            parameter_description='JSON: {"name": str, "type": "permanent"|"timeLimit"|"disposable"|"urgent", "password": str (6-12 digits), "startTime": timestamp, "endTime": timestamp}',
            requires_user_input=True,
        ),
        CommandDef(
            "deleteKey",
            parameter="",
            parameter_description='JSON: {"id": passcode_id}',
            requires_user_input=True,
        ),
    ],
    "Keypad Vision Pro": [
        CommandDef(
            "createKey",
            parameter="",
            parameter_description='JSON: {"name": str, "type": "permanent"|"timeLimit"|"disposable"|"urgent", "password": str (6-12 digits), "startTime": timestamp, "endTime": timestamp}',
            requires_user_input=True,
        ),
        CommandDef(
            "deleteKey",
            parameter="",
            parameter_description='JSON: {"id": passcode_id}',
            requires_user_input=True,
        ),
    ],
    "Blind Tilt": [
        CommandDef("fullyOpen", parameter_description="Open blinds fully"),
        CommandDef("closeUp", parameter_description="Close blinds upward (up;0)"),
        CommandDef("closeDown", parameter_description="Close blinds downward (down;0)"),
        CommandDef(
            "setPosition",
            parameter="",
            parameter_description="direction;position (e.g. up;60). direction: up/down, position: 0-100 (must be even number, 0=closed, 100=open)",
            requires_user_input=True,
        ),
    ],
    "Roller Shade": [
        CommandDef(
            "setPosition",
            parameter="",
            parameter_description="Position 0-100 (0=open, 100=closed)",
            requires_user_input=True,
        ),
    ],
    "Battery Circulator Fan": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setNightLightMode",
            parameter="",
            parameter_description="Nightlight mode",
            parameter_options=["off", "1", "2"],
        ),
        CommandDef(
            "setWindMode",
            parameter="",
            parameter_description="Fan mode",
            parameter_options=["direct", "natural", "sleep", "baby"],
        ),
        CommandDef(
            "setWindSpeed",
            parameter="",
            parameter_description="Fan speed 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "closeDelay",
            parameter="",
            parameter_description="Auto-off timer in seconds (1-36000)",
            requires_user_input=True,
        ),
    ],
    "Circulator Fan": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setNightLightMode",
            parameter="",
            parameter_description="Nightlight mode",
            parameter_options=["off", "1", "2"],
        ),
        CommandDef(
            "setWindMode",
            parameter="",
            parameter_description="Fan mode",
            parameter_options=["direct", "natural", "sleep", "baby"],
        ),
        CommandDef(
            "setWindSpeed",
            parameter="",
            parameter_description="Fan speed 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "closeDelay",
            parameter="",
            parameter_description="Auto-off timer in seconds (1-36000)",
            requires_user_input=True,
        ),
    ],
    "Standing Circulator Fan": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef(
            "setNightLightMode",
            parameter="",
            parameter_description="Nightlight mode",
            parameter_options=["off", "1", "2"],
        ),
        CommandDef(
            "setWindMode",
            parameter="",
            parameter_description="Fan mode",
            parameter_options=["direct", "natural", "sleep", "baby"],
        ),
        CommandDef(
            "setWindSpeed",
            parameter="",
            parameter_description="Fan speed 1-100",
            requires_user_input=True,
        ),
        CommandDef(
            "closeDelay",
            parameter="",
            parameter_description="Auto-off timer in seconds (1-36000)",
            requires_user_input=True,
        ),
    ],
    "Relay Switch 1PM": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description="Switch mode",
            parameter_options=["0", "1", "2", "3"],
        ),
    ],
    "Relay Switch 1": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description="Switch mode",
            parameter_options=["0", "1", "2", "3"],
        ),
    ],
    "Relay Switch 2PM": [
        CommandDef(
            "turnOn",
            parameter="",
            parameter_description="Channel number",
            parameter_options=["1", "2"],
        ),
        CommandDef(
            "turnOff",
            parameter="",
            parameter_description="Channel number",
            parameter_options=["1", "2"],
        ),
        CommandDef(
            "toggle",
            parameter="",
            parameter_description="Channel number",
            parameter_options=["1", "2"],
        ),
        CommandDef(
            "setMode",
            parameter="",
            parameter_description="channel;mode (e.g. 1;0). Channel: 1 or 2. Mode: 0=toggle, 1=edge, 2=detached, 3=momentary",
            requires_user_input=True,
        ),
        CommandDef(
            "setPosition",
            parameter="",
            parameter_description="Roller blind position 0-100 (0=open, 100=closed)",
            requires_user_input=True,
        ),
    ],
    "Garage Door Opener": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
    ],
    "Floor Lamp": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
        CommandDef(
            "setColor",
            parameter="",
            parameter_description="RGB color as R:G:B (each 0-255), e.g. 122:80:20",
            requires_user_input=True,
        ),
        CommandDef(
            "setColorTemperature",
            parameter="",
            parameter_description="Color temperature 2700-6500K",
            requires_user_input=True,
        ),
    ],
    "Video Doorbell": [
        CommandDef("enableMotionDetection", parameter_description="Enable motion detection"),
        CommandDef("disableMotionDetection", parameter_description="Disable motion detection"),
    ],
    "Candle Warmer Lamp": [
        CommandDef("turnOn", parameter_description="Set to ON state"),
        CommandDef("turnOff", parameter_description="Set to OFF state"),
        CommandDef("toggle", parameter_description="Toggle state"),
        CommandDef(
            "setBrightness",
            parameter="",
            parameter_description="Brightness level 0-100",
            requires_user_input=True,
        ),
    ],
    "AI Art Frame": [
        CommandDef("next", parameter_description="Switch to next image"),
        CommandDef("previous", parameter_description="Switch to previous image"),
    ],
}

IR_REMOTE_COMMANDS: dict[str, list[CommandDef]] = {
    "Air Conditioner": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef(
            "setAll",
            parameter="",
            parameter_description="temp,mode,fanSpeed,powerState (e.g. 26,1,3,on). mode: 1=auto, 2=cool, 3=dry, 4=fan, 5=heat. fan: 1=auto, 2=low, 3=medium, 4=high. power: on/off",
            requires_user_input=True,
        ),
    ],
    "TV": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef(
            "SetChannel",
            parameter="",
            parameter_description="Channel number (e.g. 15)",
            requires_user_input=True,
        ),
        CommandDef("volumeAdd", parameter_description="Volume up"),
        CommandDef("volumeSub", parameter_description="Volume down"),
        CommandDef("channelAdd", parameter_description="Next channel"),
        CommandDef("channelSub", parameter_description="Previous channel"),
    ],
    "IPTV/Streamer": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef(
            "SetChannel",
            parameter="",
            parameter_description="Channel number",
            requires_user_input=True,
        ),
        CommandDef("volumeAdd", parameter_description="Volume up"),
        CommandDef("volumeSub", parameter_description="Volume down"),
        CommandDef("channelAdd", parameter_description="Next channel"),
        CommandDef("channelSub", parameter_description="Previous channel"),
    ],
    "Set Top Box": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef(
            "SetChannel",
            parameter="",
            parameter_description="Channel number",
            requires_user_input=True,
        ),
        CommandDef("volumeAdd", parameter_description="Volume up"),
        CommandDef("volumeSub", parameter_description="Volume down"),
        CommandDef("channelAdd", parameter_description="Next channel"),
        CommandDef("channelSub", parameter_description="Previous channel"),
    ],
    "DVD": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef("setMute", parameter_description="Mute/unmute"),
        CommandDef("FastForward", parameter_description="Fast forward"),
        CommandDef("Rewind", parameter_description="Rewind"),
        CommandDef("Next", parameter_description="Next track"),
        CommandDef("Previous", parameter_description="Previous track"),
        CommandDef("Pause", parameter_description="Pause"),
        CommandDef("Play", parameter_description="Play/resume"),
        CommandDef("Stop", parameter_description="Stop"),
    ],
    "Speaker": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef("volumeAdd", parameter_description="Volume up"),
        CommandDef("volumeSub", parameter_description="Volume down"),
        CommandDef("setMute", parameter_description="Mute/unmute"),
        CommandDef("FastForward", parameter_description="Fast forward"),
        CommandDef("Rewind", parameter_description="Rewind"),
        CommandDef("Next", parameter_description="Next track"),
        CommandDef("Previous", parameter_description="Previous track"),
        CommandDef("Pause", parameter_description="Pause"),
        CommandDef("Play", parameter_description="Play/resume"),
        CommandDef("Stop", parameter_description="Stop"),
    ],
    "Fan": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef("swing", parameter_description="Toggle swing"),
        CommandDef("timer", parameter_description="Set timer"),
        CommandDef("lowSpeed", parameter_description="Set fan speed to low"),
        CommandDef("middleSpeed", parameter_description="Set fan speed to medium"),
        CommandDef("highSpeed", parameter_description="Set fan speed to high"),
    ],
    "Light": [
        CommandDef("turnOn", parameter_description="Turn on"),
        CommandDef("turnOff", parameter_description="Turn off"),
        CommandDef("brightnessUp", parameter_description="Brightness up"),
        CommandDef("brightnessDown", parameter_description="Brightness down"),
    ],
    "Others": [
        CommandDef(
            "",
            command_type="customize",
            parameter_description="Enter the name of a custom button configured in the SwitchBot app. Command type is automatically set to 'customize'.",
            requires_user_input=True,
        ),
    ],
}

DEVICE_TYPE_ALIASES: dict[str, str] = {
    "Hub Mini": "_hub",
    "Hub 2": "_hub",
    "Hub 3": "_hub",
    "Hub Plus": "_hub",
    "AI Hub": "_hub",
    "Remote": "_no_commands",
    "Meter": "_no_commands",
    "Meter Plus": "_no_commands",
    "Outdoor Meter": "_no_commands",
    "Meter Pro": "_no_commands",
    "Meter Pro CO2": "_no_commands",
    "Motion Sensor": "_no_commands",
    "Contact Sensor": "_no_commands",
    "Presence Sensor": "_no_commands",
    "Water Leak Detector": "_no_commands",
    "Indoor Cam": "_no_commands",
    "Pan/Tilt Cam": "_no_commands",
    "Pan/Tilt Cam 2K": "_no_commands",
    "Pan/Tilt Cam Plus 2K": "_no_commands",
    "Pan/Tilt Cam Plus 3K": "_no_commands",
    "Home Climate Panel": "_no_commands",
    "Evaporative Humidifier": "Humidifier2",
    "Evaporative Humidifier (Auto-refill)": "Humidifier2",
    "Mini Robot Vacuum K10+": "K10+",
    "Mini Robot Vacuum K10+ Pro": "K10+ Pro",
    "Multitasking Household Robot K20+ Pro": "K20+ Pro",
    "Floor Cleaning Robot S10": "Floor Cleaning Robot S10",
    "Floor Cleaning Robot S20": "S20",
    "Robot Vacuum K11+": "K11+",
    "K10+ Pro Combo": "Robot Vacuum Cleaner K10+ Pro Combo",
    "LED Strip Light 3": "Strip Light 3",
}

PARAMETER_OPTION_LABELS: dict[str, dict[str, str]] = {
    "PowLevel": {
        "0": "0 - Quiet",
        "1": "1 - Standard",
        "2": "2 - Strong",
        "3": "3 - MAX",
    },
    "setNightLightMode": {
        "off": "Off",
        "1": "1 - Bright",
        "2": "2 - Dim",
    },
    "setWindMode": {
        "direct": "Direct",
        "natural": "Natural",
        "sleep": "Sleep",
        "baby": "Ultra Quiet (Baby)",
    },
    "setMode:Relay Switch 1PM": {
        "0": "0 - Toggle mode",
        "1": "1 - Edge switch mode",
        "2": "2 - Detached switch mode",
        "3": "3 - Momentary switch mode",
    },
    "setMode:Relay Switch 1": {
        "0": "0 - Toggle mode",
        "1": "1 - Edge switch mode",
        "2": "2 - Detached switch mode",
        "3": "3 - Momentary switch mode",
    },
    "setMode:Smart Radiator Thermostat": {
        "0": "0 - Schedule mode",
        "1": "1 - Manual mode",
        "2": "2 - Power off mode",
        "3": "3 - Energy saving mode",
        "4": "4 - Comfort mode",
        "5": "5 - Quick heating mode",
    },
    "selfClean": {
        "1": "1 - Wash mop",
        "2": "2 - Dry",
        "3": "3 - Terminate",
    },
    "setChildLock:Air Purifier VOC": {
        "0": "0 - Disabled",
        "1": "1 - Enabled",
    },
    "setChildLock:Humidifier2": {
        "true": "Enabled",
        "false": "Disabled",
    },
    "turnOn:Relay Switch 2PM": {
        "1": "Channel 1",
        "2": "Channel 2",
    },
    "turnOff:Relay Switch 2PM": {
        "1": "Channel 1",
        "2": "Channel 2",
    },
    "toggle:Relay Switch 2PM": {
        "1": "Channel 1",
        "2": "Channel 2",
    },
}


def get_commands_for_device_type(
    device_type: str, *, is_infrared: bool = False
) -> list[CommandDef]:
    """Return the list of available commands for a given device type.

    Resolves aliases and falls back to a generic command set for unknown types.
    """
    if is_infrared:
        if device_type in IR_REMOTE_COMMANDS:
            return IR_REMOTE_COMMANDS[device_type]
        return IR_REMOTE_COMMANDS.get("Others", [])

    resolved = DEVICE_TYPE_ALIASES.get(device_type, device_type)

    if resolved == "_hub":
        return []
    if resolved == "_no_commands":
        return []

    return PHYSICAL_DEVICE_COMMANDS.get(resolved, [])


def get_parameter_label(command: str, value: str, device_type: str = "") -> str:
    """Return a human-readable label for a parameter option value."""
    device_key = f"{command}:{device_type}"
    if device_key in PARAMETER_OPTION_LABELS:
        return PARAMETER_OPTION_LABELS[device_key].get(value, value)
    if command in PARAMETER_OPTION_LABELS:
        return PARAMETER_OPTION_LABELS[command].get(value, value)
    return value
