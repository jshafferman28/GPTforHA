"""ChatGPT Plus HA Agent - Handles communication with the sidecar service."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    API_CHAT,
    API_NEW_CONVERSATION,
    API_STATUS,
    CONVERSATION_IDLE_MINUTES,
    SUPERVISOR_URL,
)
from .context import build_context

_LOGGER = logging.getLogger(__name__)


class ChatGPTPlusAgent:
    """Agent for communicating with ChatGPT via sidecar."""

    def __init__(self, hass: HomeAssistant, sidecar_url: str) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.sidecar_url = sidecar_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._conversation_id: str | None = None
        self._last_interaction: datetime | None = None

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
        await self._maybe_rollover_conversation()
        context_payload = await build_context(self.hass, CONVERSATION_IDLE_MINUTES)
        formatted_message = self._format_prompt(message, context_payload)

        result = await self._send_message_raw(formatted_message)

        if not result.get("success") and self._is_retryable_timeout(result):
            _LOGGER.warning("Retrying ChatGPT request after timeout")
            await self.new_conversation()
            result = await self._send_message_raw(formatted_message)

        if result.get("success"):
            self._last_interaction = dt_util.utcnow()

        return result

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
                    self._last_interaction = dt_util.utcnow()
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

    async def _maybe_rollover_conversation(self) -> None:
        if not self._last_interaction:
            return
        if dt_util.utcnow() - self._last_interaction > timedelta(
            minutes=CONVERSATION_IDLE_MINUTES
        ):
            _LOGGER.info("Conversation idle, starting a new chat")
            await self.new_conversation()

    async def _send_message_raw(self, message: str) -> dict[str, Any]:
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

    def _format_prompt(self, message: str, context_payload: dict[str, Any]) -> str:
        context_json = json.dumps(context_payload, ensure_ascii=True)
        return (
            "You are assisting a Home Assistant user.\n"
            "Use the Home Assistant context JSON below to answer.\n"
            "Do not reveal secrets or credentials. Ask clarifying questions when needed.\n\n"
            "HOME_ASSISTANT_CONTEXT_JSON:\n"
            f"{context_json}\n\n"
            "USER_REQUEST:\n"
            f"{message}"
        )

    def _is_retryable_timeout(self, result: dict[str, Any]) -> bool:
        message = str(result.get("message", "")).lower()
        return "timeout" in message

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
