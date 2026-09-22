"""Tests for the pure options-merge helpers used by the options flow.

These exercise `merge_ir_buttons` and `parse_button_lines` in
`service_generator.py` directly, without touching Home Assistant, since
`OptionsFlow` itself cannot be unit tested in this harness.
"""

from __future__ import annotations

from conftest import load_integration_module

sg = load_integration_module("service_generator")


def test_merge_preserves_unrelated_options():
    """Regression: async_create_entry replaces options wholesale."""
    options = {"service_aliases": {"office_curtain": "E1"}}
    merged = sg.merge_ir_buttons(options, "02-1", ["Bright", "Dim"])
    assert merged["service_aliases"] == {"office_curtain": "E1"}
    assert merged["ir_buttons"]["02-1"] == ["Bright", "Dim"]


def test_merge_preserves_other_devices_buttons():
    options = {"ir_buttons": {"02-1": ["Bright"], "02-2": ["Netflix"]}}
    merged = sg.merge_ir_buttons(options, "02-1", ["Bright", "Dim"])
    assert merged["ir_buttons"]["02-2"] == ["Netflix"]


def test_merge_does_not_mutate_the_input():
    options = {"ir_buttons": {"02-1": ["Bright"]}}
    sg.merge_ir_buttons(options, "02-1", ["Dim"])
    assert options["ir_buttons"]["02-1"] == ["Bright"]


def test_merge_strips_blank_lines_and_surrounding_whitespace():
    merged = sg.merge_ir_buttons({}, "02-1", ["  Bright  ", "", "Dim", "   "])
    assert merged["ir_buttons"]["02-1"] == ["Bright", "Dim"]


def test_merge_preserves_case_exactly():
    merged = sg.merge_ir_buttons({}, "02-1", ["NetFLIX", "bright"])
    assert merged["ir_buttons"]["02-1"] == ["NetFLIX", "bright"]


def test_merge_deduplicates_while_keeping_first_order():
    merged = sg.merge_ir_buttons({}, "02-1", ["Bright", "Dim", "Bright"])
    assert merged["ir_buttons"]["02-1"] == ["Bright", "Dim"]


def test_empty_list_removes_the_device_entry():
    merged = sg.merge_ir_buttons({"ir_buttons": {"02-1": ["Bright"]}}, "02-1", [])
    assert "02-1" not in merged.get("ir_buttons", {})


def test_parse_button_lines_splits_on_newlines():
    assert sg.parse_button_lines("Bright\nDim\n\nNight") == ["Bright", "Dim", "Night"]
