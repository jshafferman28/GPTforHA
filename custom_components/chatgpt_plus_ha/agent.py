"""ChatGPT Plus HA Agent - Handles communication with the sidecar service."""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_CHAT,
    API_NEW_CONVERSATION,
    API_STATUS,
    SUPERVISOR_URL,
)

_LOGGER = logging.getLogger(__name__)


class ChatGPTPlusAgent:
    """Agent for communicating with ChatGPT via sidecar."""

    def __init__(self, hass: HomeAssistant, sidecar_url: str) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.sidecar_url = sidecar_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._conversation_id: str | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get the aiohttp session."""
        if self._session is None:
            self._session = async_get_clientsession(self.hass)
        return self._session

    async def get_status(self) -> dict[str, Any]:
        """Get the current status from the sidecar."""
        try:
            headers = self._build_headers()
            async with self.session.get(
                f"{self.sidecar_url}{API_STATUS}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"error": f"Status {response.status}"}
        except Exception as e:
            _LOGGER.error("Error getting status: %s", e)
            return {"error": str(e)}

    async def send_message(self, message: str) -> dict[str, Any]:
        """Send a message to ChatGPT and get the response."""
        try:
            payload = {"message": message}
            if self._conversation_id:
                payload["conversationId"] = self._conversation_id

            headers = self._build_headers()
            async with self.session.post(
                f"{self.sidecar_url}{API_CHAT}",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=180),  # 3 minute timeout for long responses
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("conversationId"):
                        self._conversation_id = data["conversationId"]
                    return data
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", f"Status {response.status}"),
                        "message": error_data.get("message", "Unknown error"),
                    }
        except aiohttp.ClientTimeout:
            _LOGGER.error("Timeout waiting for ChatGPT response")
            return {
                "success": False,
                "error": "timeout",
                "message": "ChatGPT took too long to respond",
            }
        except Exception as e:
            _LOGGER.error("Error sending message: %s", e)
            return {
                "success": False,
                "error": "exception",
                "message": str(e),
            }

    async def new_conversation(self) -> dict[str, Any]:
        """Start a new conversation."""
        try:
            headers = self._build_headers()
            async with self.session.post(
                f"{self.sidecar_url}{API_NEW_CONVERSATION}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._conversation_id = None
                    return data
                else:
                    error_data = await response.json()
                    return {
                        "success": False,
                        "error": error_data.get("error", f"Status {response.status}"),
                    }
        except Exception as e:
            _LOGGER.error("Error starting new conversation: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    @property
    def conversation_id(self) -> str | None:
        """Get the current conversation ID."""
        return self._conversation_id

    def _build_headers(self) -> dict[str, str]:
        token = os.environ.get("SUPERVISOR_TOKEN")
        if not token:
            return {}

        try:
            target = urlparse(self.sidecar_url)
            supervisor = urlparse(os.environ.get("SUPERVISOR_URL", SUPERVISOR_URL))
        except ValueError:
            return {}

        if target.hostname and target.hostname == supervisor.hostname:
            return {"Authorization": f"Bearer {token}"}

        return {}
