"""Config flow for SwitchBot API integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import SwitchBotApiError, async_request
from .const import CONF_SECRET, CONF_TOKEN, DOMAIN
from .services import fetch_devices

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_SECRET): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate credentials by calling the SwitchBot API."""
    token = data[CONF_TOKEN].strip()
    secret = data[CONF_SECRET].strip()
    if not token or not secret:
        raise InvalidAuth

    try:
        await async_request(hass, "GET", "/devices", token, secret)
    except SwitchBotApiError as exc:
        if exc.auth_failed:
            raise InvalidAuth from exc
        raise CannotConnect from exc

    return {"title": "SwitchBot API"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot API."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="SwitchBot API",
                    data={
                        CONF_TOKEN: user_input[CONF_TOKEN].strip(),
                        CONF_SECRET: user_input[CONF_SECRET].strip(),
                    },
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle credential update when the user reconfigures the integration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data={
                        CONF_TOKEN: user_input[CONF_TOKEN].strip(),
                        CONF_SECRET: user_input[CONF_SECRET].strip(),
                    },
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SwitchBotAuthOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SwitchBotAuthOptionsFlowHandler()


class SwitchBotAuthOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SwitchBot API options - displays device summary when user opens integration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Display device summary when user opens integration config."""
        if user_input is not None:
            return self.async_create_entry(data={})

        try:
            result = await fetch_devices(self.hass, self.config_entry)
        except SwitchBotApiError as exc:
            result = {
                "device_count": 0,
                "physical_device_count": 0,
                "infrared_remote_count": 0,
                "devices": [],
            }
            _LOGGER.warning("Could not fetch devices in options flow: %s", exc)

        physical = []
        infrared = []
        for device in result.get("devices", []):
            line = f"• **{device['device_name']}** ({device['device_type']}) `{device['device_id']}`"
            if device.get("is_infrared"):
                infrared.append(line)
            else:
                physical.append(line)

        sections = []
        if physical:
            sections.append("**Physical devices:**\n" + "\n".join(physical))
        if infrared:
            sections.append("**Infrared remotes:**\n" + "\n".join(infrared))
        if not sections:
            sections.append("No devices found in this SwitchBot account.")

        devices_text = "\n\n".join(sections)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_count": str(result["device_count"]),
                "physical_device_count": str(result["physical_device_count"]),
                "infrared_remote_count": str(result["infrared_remote_count"]),
                "devices": devices_text,
            },
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect to the API."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""
