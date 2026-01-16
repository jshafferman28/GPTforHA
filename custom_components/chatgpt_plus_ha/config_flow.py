"""Config flow for ChatGPT Plus HA integration."""

from __future__ import annotations

import logging
import os
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
    ADDON_SLUG,
    DEFAULT_SIDECAR_PORT,
    SUPERVISOR_URL,
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

            session = async_get_clientsession(self.hass)
            errors = await self._validate_sidecar(session, sidecar_url)

            if errors:
                fallback_url = await self._get_supervisor_sidecar_url(session)
                if fallback_url and fallback_url != sidecar_url:
                    _LOGGER.debug(
                        "Falling back to supervisor sidecar URL: %s", fallback_url
                    )
                    fallback_errors = await self._validate_sidecar(
                        session, fallback_url
                    )
                    if not fallback_errors:
                        sidecar_url = fallback_url
                        errors = {}

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

    async def _validate_sidecar(
        self, session: aiohttp.ClientSession, sidecar_url: str
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        try:
            async with session.get(
                f"{sidecar_url}{API_HEALTH}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return {"base": "cannot_connect"}

                health_data = await response.json()
                if health_data.get("status") != "healthy":
                    return {"base": "sidecar_not_ready"}

            async with session.get(
                f"{sidecar_url}{API_STATUS}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return {"base": "cannot_connect"}

                status_data = await response.json()
                if not status_data.get("isLoggedIn"):
                    return {"base": "not_logged_in"}

        except aiohttp.ClientConnectorError:
            return {"base": "cannot_connect"}
        except aiohttp.ClientTimeout:
            return {"base": "timeout"}
        except Exception:
            _LOGGER.exception("Unexpected error validating sidecar")
            return {"base": "unknown"}

        return errors

    async def _get_supervisor_sidecar_url(
        self, session: aiohttp.ClientSession
    ) -> str | None:
        token = os.environ.get("SUPERVISOR_TOKEN")
        if not token:
            return None

        supervisor_url = os.environ.get("SUPERVISOR_URL", SUPERVISOR_URL).rstrip("/")
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with session.get(
                f"{supervisor_url}/addons/{ADDON_SLUG}/info",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return None

                payload = await response.json()
        except Exception as err:
            _LOGGER.debug("Supervisor add-on lookup failed: %s", err)
            return None

        info = payload.get("data") or {}
        hostname = info.get("hostname")
        ip_address = info.get("ip_address")

        if hostname:
            return f"http://{hostname}:{DEFAULT_SIDECAR_PORT}"
        if ip_address:
            return f"http://{ip_address}:{DEFAULT_SIDECAR_PORT}"

        return None

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
