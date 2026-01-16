"""Config flow for ChatGPT Plus HA integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SIDECAR_URL,
    DEFAULT_SIDECAR_URL,
    DOMAIN,
    API_HEALTH,
    API_STATUS,
)

_LOGGER = logging.getLogger(__name__)


class ChatGPTPlusHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ChatGPT Plus HA."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            sidecar_url = user_input[CONF_SIDECAR_URL].rstrip("/")

            # Validate connection to sidecar
            try:
                session = async_get_clientsession(self.hass)
                
                # Check health endpoint
                async with session.get(
                    f"{sidecar_url}{API_HEALTH}", timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        errors["base"] = "cannot_connect"
                    else:
                        health_data = await response.json()
                        if health_data.get("status") != "healthy":
                            errors["base"] = "sidecar_not_ready"

                # Check auth status
                if not errors:
                    async with session.get(
                        f"{sidecar_url}{API_STATUS}", timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status != 200:
                            errors["base"] = "cannot_connect"
                        else:
                            status_data = await response.json()
                            if not status_data.get("isLoggedIn"):
                                errors["base"] = "not_logged_in"

            except aiohttp.ClientConnectorError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientTimeout:
                errors["base"] = "timeout"
            except Exception:
                _LOGGER.exception("Unexpected error validating sidecar")
                errors["base"] = "unknown"

            if not errors:
                # Create entry
                await self.async_set_unique_id(f"chatgpt_plus_ha_{sidecar_url}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="ChatGPT Plus HA",
                    data={CONF_SIDECAR_URL: sidecar_url},
                )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SIDECAR_URL, default=DEFAULT_SIDECAR_URL
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ChatGPTPlusHAOptionsFlowHandler:
        """Get the options flow for this handler."""
        return ChatGPTPlusHAOptionsFlowHandler(config_entry)


class ChatGPTPlusHAOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ChatGPT Plus HA."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SIDECAR_URL,
                        default=self.config_entry.data.get(
                            CONF_SIDECAR_URL, DEFAULT_SIDECAR_URL
                        ),
                    ): str,
                }
            ),
        )
