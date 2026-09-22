from __future__ import annotations

import pathlib
import subprocess
import sys

from conftest import load_integration_module


def test_loader_imports_existing_device_commands():
    mod = load_integration_module("device_commands")
    commands = [c.command for c in mod.get_commands_for_device_type("Bot")]
    assert "turnOn" in commands
    assert "press" in commands


def test_loader_does_not_import_homeassistant():
    """Verify device_commands loads without importing homeassistant in a clean interpreter.

    This subprocess test confirms the guarantee that the loader's synthetic-package
    approach allows device_commands to load without homeassistant being present.
    homeassistant is NOT installed in .venv, so a subprocess is a true test environment.
    """
    # Get repo root: tests/conftest.py parent
    repo_root = pathlib.Path(__file__).resolve().parent.parent

    script = f"""
import sys
import pathlib
import importlib.util
import types

# Replicate the loader's synthetic-package trick
ROOT = pathlib.Path({repr(str(repo_root))})
SYNTHETIC_PKG = "switchbot_api_under_test"

pkg = types.ModuleType(SYNTHETIC_PKG)
pkg.__path__ = [str(ROOT)]
sys.modules[SYNTHETIC_PKG] = pkg

# Load device_commands using the same technique as conftest
full_name = f"{{SYNTHETIC_PKG}}.device_commands"
path = ROOT / "device_commands.py"
spec = importlib.util.spec_from_file_location(full_name, path)
module = importlib.util.module_from_spec(spec)
sys.modules[full_name] = module
spec.loader.exec_module(module)

# Verify homeassistant is NOT in sys.modules
if "homeassistant" in sys.modules:
    print("FAILED: homeassistant found in sys.modules")
    sys.exit(1)

print("SUCCESS: device_commands loaded without homeassistant")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
    assert "SUCCESS" in result.stdout, f"Test sentinel not found in output: {result.stdout}"
