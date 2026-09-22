"""Hand-written labels and schema fixes layered over the generated index.

Survives regeneration of command_index.py. Keys are "<device type>:<command>".
Values are CommandDef field names; `fields` replaces the generated tuple
entirely, other keys patch individual attributes.
"""

from __future__ import annotations

from .command_types import ParamField

COMMAND_OVERLAY: dict[str, dict] = {
    "Curtain:turnOn": {"label": "Open curtain"},
    "Curtain:turnOff": {"label": "Close curtain"},
    "Curtain:pause": {"label": "Pause movement"},
    "Curtain:setPosition": {
        "label": "Move to position",
        "fields": (
            ParamField(key="index", label="Curtain", kind="number", default="0",
                       minimum=0, maximum=8,
                       help="Which curtain in a paired group. 0 unless grouped."),
            ParamField(key="mode", label="Mode", kind="select", default="ff",
                       options=(("ff", "Default"), ("0", "Performance"),
                                ("1", "Silent"))),
            ParamField(key="position", label="Position", kind="number",
                       minimum=0, maximum=100, unit="%",
                       help="0 is fully open, 100 is fully closed."),
        ),
    },
    "Curtain 3:turnOn": {"label": "Open curtain"},
    "Curtain 3:turnOff": {"label": "Close curtain"},
    "Curtain 3:pause": {"label": "Pause movement"},
    "Curtain 3:setPosition": {
        "label": "Move to position",
        "fields": (
            ParamField(key="index", label="Curtain", kind="number", default="0",
                       minimum=0, maximum=8,
                       help="Which curtain in a paired group. 0 unless grouped."),
            ParamField(key="mode", label="Mode", kind="select", default="ff",
                       options=(("ff", "Default"), ("0", "Performance"),
                                ("1", "Silent"))),
            ParamField(key="position", label="Position", kind="number",
                       minimum=0, maximum=100, unit="%",
                       help="0 is fully open, 100 is fully closed."),
        ),
    },
    "Smart Lock:lock": {"label": "Lock"},
    "Smart Lock:unlock": {"label": "Unlock"},
    "Air Conditioner:setAll": {
        "label": "Set temperature, mode and fan",
        "fields": (
            ParamField(key="temperature", label="Temperature", kind="number",
                       default="26", minimum=16, maximum=30, unit="°C"),
            ParamField(key="mode", label="Mode", kind="select", default="2",
                       options=(("1", "Auto"), ("2", "Cool"), ("3", "Dry"),
                                ("4", "Fan"), ("5", "Heat"))),
            ParamField(key="fan_speed", label="Fan speed", kind="select",
                       default="1",
                       options=(("1", "Auto"), ("2", "Low"), ("3", "Medium"),
                                ("4", "High"))),
            ParamField(key="power_state", label="Power", kind="select",
                       default="on", options=(("on", "On"), ("off", "Off"))),
        ),
    },
}

# Device types that resolve to another type's command set, or to no commands.
# Copied verbatim from the pre-4.0.0 device_commands.py.
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
