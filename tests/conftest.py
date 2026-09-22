"""Load integration modules for tests without importing Home Assistant.

The repository root is the integration package, and its __init__.py imports
homeassistant. A synthetic parent package lets relative imports inside the
modules under test resolve without __init__.py ever running.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types


def _mock_homeassistant():
    """Set up fake homeassistant and other modules before pytest imports."""
    class StubClass:
        pass

    # Create modules
    homeassistant = types.ModuleType("homeassistant")
    config_entries_mod = types.ModuleType("config_entries")
    const_mod = types.ModuleType("const")
    core_mod = types.ModuleType("core")
    exceptions_mod = types.ModuleType("exceptions")
    helpers_mod = types.ModuleType("helpers")
    entity_registry_mod = types.ModuleType("entity_registry")
    aiohttp_client_mod = types.ModuleType("aiohttp_client")
    vol_mod = types.ModuleType("voluptuous")

    # Add stub classes to homeassistant modules
    config_entries_mod.ConfigEntry = StubClass
    config_entries_mod.ConfigEntryState = type("ConfigEntryState", (), {})

    # Create Platform enum with attributes
    class Platform:
        BUTTON = "button"
        SENSOR = "sensor"
    const_mod.Platform = Platform
    core_mod.HomeAssistant = StubClass
    core_mod.ServiceCall = StubClass
    core_mod.ServiceResponse = StubClass
    core_mod.SupportsResponse = type("SupportsResponse", (), {})
    core_mod.callback = lambda f: f
    exceptions_mod.ServiceValidationError = type("ServiceValidationError", (Exception,), {})

    # Add stubs to voluptuous
    vol_mod.Required = StubClass
    vol_mod.Optional = StubClass
    vol_mod.Schema = StubClass
    vol_mod.All = StubClass
    vol_mod.Any = StubClass
    vol_mod.In = StubClass

    # Add stubs to aiohttp
    aiohttp_mod = types.ModuleType("aiohttp")
    aiohttp_mod.ClientError = type("ClientError", (Exception,), {})
    aiohttp_mod.ClientSession = StubClass
    aiohttp_mod.ClientResponse = StubClass

    # Add stubs to requests
    requests_mod = types.ModuleType("requests")
    requests_mod.Session = StubClass
    requests_mod.get = StubClass
    requests_mod.post = StubClass

    # Add stubs to homeassistant.helpers.aiohttp_client
    aiohttp_client_mod.async_get_clientsession = StubClass

    # homeassistant.helpers.service, for async_set_service_schema
    service_mod = types.ModuleType("service")
    service_mod.async_set_service_schema = lambda *args, **kwargs: None

    # homeassistant.helpers.config_validation, for CONFIG_SCHEMA
    cv_mod = types.ModuleType("config_validation")
    cv_mod.config_entry_only_config_schema = lambda domain: None

    # Register all modules in sys.modules
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries_mod
    sys.modules["homeassistant.const"] = const_mod
    sys.modules["homeassistant.core"] = core_mod
    sys.modules["homeassistant.exceptions"] = exceptions_mod
    sys.modules["homeassistant.helpers"] = helpers_mod
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry_mod
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client_mod
    sys.modules["homeassistant.helpers.service"] = service_mod
    sys.modules["homeassistant.helpers.config_validation"] = cv_mod
    sys.modules["voluptuous"] = vol_mod
    sys.modules["aiohttp"] = aiohttp_mod
    sys.modules["requests"] = requests_mod

    # Set attributes on modules for dot-notation access
    homeassistant.config_entries = config_entries_mod
    homeassistant.const = const_mod
    homeassistant.core = core_mod
    homeassistant.exceptions = exceptions_mod
    homeassistant.helpers = helpers_mod
    helpers_mod.entity_registry = entity_registry_mod
    helpers_mod.aiohttp_client = aiohttp_client_mod
    helpers_mod.service = service_mod
    helpers_mod.config_validation = cv_mod


# Don't mock at module level; do it in a pytest hook instead
# This allows individual tests to verify homeassistant doesn't get imported

ROOT = pathlib.Path(__file__).resolve().parents[1]
SYNTHETIC_PKG = "switchbot_api_under_test"


def _ensure_package() -> None:
    if SYNTHETIC_PKG in sys.modules:
        return
    pkg = types.ModuleType(SYNTHETIC_PKG)
    pkg.__path__ = [str(ROOT)]
    sys.modules[SYNTHETIC_PKG] = pkg


def load_integration_module(name: str):
    """Import <repo root>/<name>.py with relative imports working."""
    _ensure_package()
    full_name = f"{SYNTHETIC_PKG}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    path = ROOT / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"no module at {path}")
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def load_tool_module(name: str):
    """Import <repo root>/tools/<name>.py as a standalone module."""
    path = ROOT / "tools" / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"no module at {path}")
    full_name = f"switchbot_api_tools_{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


import pytest


def pytest_configure(config):
    """Mock homeassistant modules before test execution."""
    _mock_homeassistant()
