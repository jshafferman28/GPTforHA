"""The ChatGPT Plus HA integration."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .agent import ChatGPTPlusAgent
from .const import CONF_SIDECAR_URL, DOMAIN

PLATFORMS: list[str] = ["ai_task"]

_LOGGER = logging.getLogger(__name__)

# Config schema - this integration only supports config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Service schemas
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_NEW_CONVERSATION = "new_conversation"

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("request_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ChatGPT Plus HA component."""
    hass.data.setdefault(
        DOMAIN,
        {
            "_panel_registered": False,
            "_services_registered": False,
        },
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChatGPT Plus HA from a config entry."""
    sidecar_url = entry.data[CONF_SIDECAR_URL]

    # Create agent
    agent = ChatGPTPlusAgent(hass, sidecar_url)

    # Store agent
    hass.data[DOMAIN][entry.entry_id] = {
        "agent": agent,
        "sidecar_url": sidecar_url,
    }

    # Register frontend panel
    if not hass.data[DOMAIN].get("_panel_registered"):
        await _async_register_panel(hass)
        hass.data[DOMAIN]["_panel_registered"] = True

    # Register services
    if not hass.data[DOMAIN].get("_services_registered"):
        await _async_register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("ChatGPT Plus HA integration set up successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    has_entries = any(
        isinstance(entry_data, dict) and "agent" in entry_data
        for entry_data in hass.data[DOMAIN].values()
    )

    if not has_entries:
        if hass.data[DOMAIN].get("_panel_registered"):
            await _async_unregister_panel(hass)
            hass.data[DOMAIN]["_panel_registered"] = False
        if hass.data[DOMAIN].get("_services_registered"):
            _async_unregister_services(hass)
            hass.data[DOMAIN]["_services_registered"] = False

    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the frontend panel."""
    frontend_path = Path(__file__).parent / "frontend"

    # Register static path for frontend files
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"/chatgpt_plus_ha/frontend",
                str(frontend_path),
                cache_headers=False,
            )
        ]
    )

    # Register panel
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="ChatGPT",
        sidebar_icon="mdi:robot",
        frontend_url_path="chatgpt-plus",
        config={
            "_panel_custom": {
                "name": "chatgpt-plus-panel",
                "module_url": "/chatgpt_plus_ha/frontend/chat-panel.js",
            }
        },
        require_admin=False,
    )


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def handle_send_message(call: ServiceCall) -> dict:
        """Handle the send_message service call."""
        message = call.data["message"]
        request_id = call.data.get("request_id")

        # Get the first available agent
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and "agent" in entry_data:
                agent: ChatGPTPlusAgent = entry_data["agent"]
                result = await agent.send_message(message)

                # Fire an event with the response
                hass.bus.async_fire(
                    f"{DOMAIN}_response",
                    {
                        "message": message,
                        "response": result.get("message", ""),
                        "success": result.get("success", False),
                        "conversation_id": result.get("conversationId"),
                        "request_id": request_id,
                    },
                )
                return result

        _LOGGER.error("No ChatGPT Plus HA agent available")
        return {"success": False, "error": "No agent available"}

    async def handle_new_conversation(call: ServiceCall) -> dict:
        """Handle the new_conversation service call."""
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and "agent" in entry_data:
                agent: ChatGPTPlusAgent = entry_data["agent"]
                return await agent.new_conversation()

        _LOGGER.error("No ChatGPT Plus HA agent available")
        return {"success": False, "error": "No agent available"}

    # Register services if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            handle_send_message,
            schema=SEND_MESSAGE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_NEW_CONVERSATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_NEW_CONVERSATION,
            handle_new_conversation,
        )


async def _async_unregister_panel(hass: HomeAssistant) -> None:
    """Unregister the frontend panel."""
    async_remove_panel(hass, "chatgpt-plus")


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    if hass.services.has_service(DOMAIN, SERVICE_NEW_CONVERSATION):
        hass.services.async_remove(DOMAIN, SERVICE_NEW_CONVERSATION)
