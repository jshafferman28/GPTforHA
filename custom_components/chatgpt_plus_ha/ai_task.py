"""AI Task entities for ChatGPT Plus HA."""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.ai_task import (
    AITaskEntity,
    AITaskEntityFeature,
    GenDataTask,
    GenDataTaskResult,
    GenImageTask,
    GenImageTaskResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .agent import ChatGPTPlusAgent
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up AI task entities from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    agent: ChatGPTPlusAgent = entry_data["agent"]
    sidecar_url = entry_data["sidecar_url"]

    async_add_entities(
        [
            ChatGPTPlusAITaskEntity(
                agent=agent,
                entry_id=entry.entry_id,
                sidecar_url=sidecar_url,
            )
        ]
    )


class ChatGPTPlusAITaskEntity(AITaskEntity):
    """AI Task entity backed by ChatGPT Plus."""

    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA

    def __init__(self, agent: ChatGPTPlusAgent, entry_id: str, sidecar_url: str) -> None:
        """Initialize the entity."""
        self._agent = agent
        self._attr_unique_id = f"{entry_id}_ai_task"
        self._attr_name = "ChatGPT Plus AI Tasks"
        self._attr_extra_state_attributes = {"sidecar_url": sidecar_url}

    async def _async_generate_data(
        self,
        task: GenDataTask,
        chat_log,
    ) -> GenDataTaskResult:
        """Generate data for the task using ChatGPT."""
        prompt = self._build_prompt(task)
        result = await self._agent.send_message(prompt)

        if not result.get("success"):
            raise RuntimeError(result.get("message", "ChatGPT request failed"))

        response_text = result.get("message", "")
        data = self._coerce_response(task, response_text)
        return GenDataTaskResult(
            conversation_id=result.get("conversationId", ""),
            data=data,
        )

    async def _async_generate_image(
        self,
        task: GenImageTask,
        chat_log,
    ) -> GenImageTaskResult:
        """Generate an image for the task."""
        raise NotImplementedError("Image generation is not supported yet.")

    def _build_prompt(self, task: GenDataTask) -> str:
        if not task.structure:
            return task.instructions

        return (
            "You are generating structured data for Home Assistant.\n"
            "Return ONLY valid JSON that matches the requested structure.\n"
            f"Instructions: {task.instructions}\n"
        )

    def _coerce_response(self, task: GenDataTask, response_text: str) -> Any:
        if not task.structure:
            return response_text.strip()

        json_payload = self._extract_json(response_text)
        if json_payload is None:
            _LOGGER.warning("Failed to parse JSON from response, returning text.")
            return response_text.strip()

        try:
            return json.loads(json_payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON payload from response, returning text.")
            return response_text.strip()

    def _extract_json(self, text: str) -> str | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1].strip()
