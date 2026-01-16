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
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .agent import ChatGPTPlusAgent
from .const import (
    CONF_SIDECAR_URL,
    CONF_CONTEXT_ENABLED,
    CONF_INCLUDE_HISTORY,
    CONF_INCLUDE_LOGBOOK,
    CONF_HISTORY_HOURS,
    CONF_ALLOWLIST_DOMAINS,
    CONF_DENYLIST_DOMAINS,
    CONF_ALLOWLIST_ENTITIES,
    CONF_DENYLIST_ENTITIES,
    CONF_MAX_CONTEXT_ENTITIES,
    CONF_SUMMARY_CACHE_TTL,
    CONF_INCOGNITO_MODE,
    DEFAULT_CONTEXT_ENABLED,
    DEFAULT_INCLUDE_HISTORY,
    DEFAULT_INCLUDE_LOGBOOK,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_ALLOWLIST_DOMAINS,
    DEFAULT_DENYLIST_DOMAINS,
    DEFAULT_ALLOWLIST_ENTITIES,
    DEFAULT_DENYLIST_ENTITIES,
    DEFAULT_MAX_CONTEXT_ENTITIES,
    DEFAULT_SUMMARY_CACHE_TTL,
    DEFAULT_INCOGNITO_MODE,
    DOMAIN,
)
from .context import build_context
from .service_helpers import (
    build_notification_template,
    extract_json_payload,
    validate_automation_yaml,
)

PLATFORMS: list[str] = ["ai_task"]

_LOGGER = logging.getLogger(__name__)

# Config schema - this integration only supports config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Service schemas
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_NEW_CONVERSATION = "new_conversation"
SERVICE_BUILD_CONTEXT = "build_context"
SERVICE_GENERATE_AUTOMATION = "generate_automation"
SERVICE_COMPOSE_NOTIFICATION = "compose_notification"

SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("request_id"): cv.string,
        vol.Optional("include_context"): cv.boolean,
        vol.Optional("include_history"): cv.boolean,
        vol.Optional("include_logbook"): cv.boolean,
        vol.Optional("history_hours"): vol.Coerce(int),
        vol.Optional("focus_areas"): cv.ensure_list,
        vol.Optional("focus_entities"): cv.ensure_list,
        vol.Optional("recent_mode"): cv.boolean,
        vol.Optional("incognito"): cv.boolean,
    }
)

BUILD_CONTEXT_SCHEMA = vol.Schema(
    {
        vol.Optional("question", default=""): cv.string,
        vol.Optional("include_history"): cv.boolean,
        vol.Optional("include_logbook"): cv.boolean,
        vol.Optional("history_hours"): vol.Coerce(int),
        vol.Optional("focus_areas"): cv.ensure_list,
        vol.Optional("focus_entities"): cv.ensure_list,
        vol.Optional("recent_mode"): cv.boolean,
        vol.Optional("summary_only"): cv.boolean,
        vol.Optional("include_suggestions"): cv.boolean,
    }
)

GENERATE_AUTOMATION_SCHEMA = vol.Schema(
    {
        vol.Optional("description"): cv.string,
        vol.Optional("mode", default="generate"): vol.In(["generate", "validate"]),
        vol.Optional("yaml"): cv.string,
        vol.Optional("include_context"): cv.boolean,
        vol.Optional("include_history"): cv.boolean,
        vol.Optional("include_logbook"): cv.boolean,
        vol.Optional("history_hours"): vol.Coerce(int),
    }
)

COMPOSE_NOTIFICATION_SCHEMA = vol.Schema(
    {
        vol.Required("event_type"): cv.string,
        vol.Optional("entities"): cv.ensure_list,
        vol.Optional("urgency", default="normal"): vol.In(
            ["low", "normal", "high"]
        ),
        vol.Optional("photo_url"): cv.string,
        vol.Optional("include_context"): cv.boolean,
        vol.Optional("include_history"): cv.boolean,
        vol.Optional("include_logbook"): cv.boolean,
        vol.Optional("history_hours"): vol.Coerce(int),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ChatGPT Plus HA component."""
    hass.data.setdefault(
        DOMAIN,
        {
            "_panel_registered": False,
            "_services_registered": False,
            "summary_cache": {},
            "recent_responses": [],
        },
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChatGPT Plus HA from a config entry."""
    sidecar_url = entry.options.get(CONF_SIDECAR_URL, entry.data[CONF_SIDECAR_URL])

    # Create agent
    agent = ChatGPTPlusAgent(hass, sidecar_url)
    merged_options = _merge_options(entry)
    agent.update_options(
        _build_context_options(
            merged_options,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    )

    # Store agent
    hass.data[DOMAIN][entry.entry_id] = {
        "agent": agent,
        "sidecar_url": sidecar_url,
        "options": merged_options,
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

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

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


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not isinstance(data, dict):
        return
    merged_options = _merge_options(entry)
    data["options"] = merged_options
    agent = data.get("agent")
    if isinstance(agent, ChatGPTPlusAgent):
        agent.update_options(
            _build_context_options(
                merged_options,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
        )


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
        include_context = call.data.get("include_context")
        include_history = call.data.get("include_history")
        include_logbook = call.data.get("include_logbook")
        history_hours = call.data.get("history_hours")
        focus_areas = call.data.get("focus_areas")
        focus_entities = call.data.get("focus_entities")
        recent_mode = call.data.get("recent_mode")
        incognito = call.data.get("incognito")

        # Get the first available agent
        for _entry_id, entry_data in _iter_agents(hass):
            agent: ChatGPTPlusAgent = entry_data["agent"]
            options = dict(entry_data.get("options") or {})
            context_options = _build_context_options(
                options,
                include_context,
                include_history,
                include_logbook,
                history_hours,
                focus_areas,
                focus_entities,
                recent_mode,
                incognito,
            )
            result = await agent.send_message(message, context_options)

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
            _store_response(hass, entry_data, message, result)
            return result

        _LOGGER.error("No ChatGPT Plus HA agent available")
        return {"success": False, "error": "No agent available"}

    async def handle_new_conversation(call: ServiceCall) -> dict:
        """Handle the new_conversation service call."""
        for _entry_id, entry_data in _iter_agents(hass):
            agent: ChatGPTPlusAgent = entry_data["agent"]
            return await agent.new_conversation()

        _LOGGER.error("No ChatGPT Plus HA agent available")
        return {"success": False, "error": "No agent available"}

    async def handle_build_context(call: ServiceCall) -> dict:
        """Build a context payload for a query."""
        question = call.data.get("question", "")
        for entry_id, entry_data in _iter_agents(hass):
            options = dict(entry_data.get("options") or {})
            context_options = _build_context_options(
                options,
                call.data.get("include_context"),
                call.data.get("include_history"),
                call.data.get("include_logbook"),
                call.data.get("history_hours"),
                call.data.get("focus_areas"),
                call.data.get("focus_entities"),
                call.data.get("recent_mode"),
                call.data.get("incognito"),
            )
            summary_only = bool(call.data.get("summary_only"))
            context_options["summary_only"] = summary_only

            if summary_only and not options.get(CONF_INCOGNITO_MODE):
                cache = hass.data[DOMAIN].setdefault("summary_cache", {}).get(entry_id)
                if cache:
                    cached_at = dt_util.parse_datetime(cache["timestamp"])
                    if cached_at:
                        age = dt_util.utcnow() - cached_at
                        if age.total_seconds() <= options.get(
                            CONF_SUMMARY_CACHE_TTL, DEFAULT_SUMMARY_CACHE_TTL
                        ):
                            context = dict(cache["data"])
                            if call.data.get("include_suggestions"):
                                context["recent_suggestions"] = _get_recent_responses(
                                    hass, options
                                )
                            return context

            context = await build_context(hass, question, context_options)
            if summary_only and not options.get(CONF_INCOGNITO_MODE):
                hass.data[DOMAIN]["summary_cache"][entry_id] = {
                    "timestamp": dt_util.utcnow().isoformat(),
                    "data": context,
                }
            if call.data.get("include_suggestions"):
                context["recent_suggestions"] = _get_recent_responses(hass, options)
            return context
        return {"error": "No agent available"}

    async def handle_generate_automation(call: ServiceCall) -> dict:
        """Generate or validate an automation."""
        mode = call.data.get("mode", "generate")
        yaml_input = call.data.get("yaml")
        description = call.data.get("description", "")

        if mode == "validate":
            if not yaml_input:
                return {
                    "success": False,
                    "error": "missing_yaml",
                    "message": "Provide yaml for validation.",
                }
            validation = validate_automation_yaml(yaml_input)
            return {"success": validation["valid"], "validation": validation}

        context_payload = await build_context(
            hass,
            description,
            {
                "context_enabled": call.data.get("include_context", True),
                "include_history": call.data.get("include_history"),
                "include_logbook": call.data.get("include_logbook"),
                "history_hours": call.data.get("history_hours"),
                "summary_only": True,
            },
        )

        prompt = (
            "You are a Home Assistant automation expert.\n"
            "Return a JSON object with keys: yaml, explanation, assumptions, questions_if_needed.\n"
            "YAML must be a single automation mapping (not a list) using modern HA schema.\n"
            "Avoid deprecated fields. Keep actions safe.\n\n"
            "HOME_CONTEXT_SUMMARY:\n"
            f"{context_payload.get('summary','')}\n\n"
            "USER_REQUEST:\n"
            f"{description}"
        )

        for _entry_id, entry_data in _iter_agents(hass):
            agent: ChatGPTPlusAgent = entry_data["agent"]
            result = await agent.send_message(
                prompt,
                {"context_enabled": False},
            )
            if not result.get("success"):
                return result

            payload = extract_json_payload(result.get("message", ""))
            if not payload:
                return {
                    "success": False,
                    "error": "invalid_response",
                    "message": "Failed to parse JSON from response.",
                }

            yaml_text = payload.get("yaml", "")
            validation = validate_automation_yaml(yaml_text) if yaml_text else {
                "valid": False,
                "errors": ["Missing YAML output."],
                "warnings": [],
                "config": None,
            }

            response = {
                "success": True,
                "yaml": yaml_text,
                "explanation": payload.get("explanation", ""),
                "assumptions": payload.get("assumptions", ""),
                "questions_if_needed": payload.get("questions_if_needed", ""),
                "validation": validation,
            }
            _store_response(hass, entry_data, description, response)
            return response

        return {"success": False, "error": "No agent available"}

    async def handle_compose_notification(call: ServiceCall) -> dict:
        """Compose a notification message without sending it."""
        event_type = call.data["event_type"]
        entities = call.data.get("entities", [])
        urgency = call.data.get("urgency", "normal")
        photo_url = call.data.get("photo_url")

        template = build_notification_template(event_type)
        if template:
            message = template["message"]
            if entities:
                message += f" Entities: {', '.join(entities)}."
            if urgency == "high":
                message = "URGENT: " + message
            response = {
                "success": True,
                "title": template["title"],
                "message": message,
                "actions": template["actions"],
                "follow_up_questions": template["questions"],
                "used_template": True,
                "photo_url": photo_url,
            }
            _store_response(hass, None, event_type, response)
            return response

        context_payload = await build_context(
            hass,
            f"Compose a notification for {event_type}",
            {
                "context_enabled": call.data.get("include_context", True),
                "include_history": call.data.get("include_history"),
                "include_logbook": call.data.get("include_logbook"),
                "history_hours": call.data.get("history_hours"),
                "summary_only": True,
            },
        )

        prompt = (
            "Generate a concise, actionable notification.\n"
            "Return JSON with keys: title, message, actions, follow_up_questions.\n"
            f"Urgency: {urgency}\n"
            f"Event type: {event_type}\n"
            f"Entities: {', '.join(entities) if entities else 'none'}\n"
            f"Context summary: {context_payload.get('summary','')}\n"
        )

        for _entry_id, entry_data in _iter_agents(hass):
            agent: ChatGPTPlusAgent = entry_data["agent"]
            result = await agent.send_message(prompt, {"context_enabled": False})
            if not result.get("success"):
                return result
            payload = extract_json_payload(result.get("message", ""))
            if not payload:
                return {
                    "success": False,
                    "error": "invalid_response",
                    "message": "Failed to parse JSON from response.",
                }
            response = {
                "success": True,
                "title": payload.get("title", "Notification"),
                "message": payload.get("message", ""),
                "actions": payload.get("actions", []),
                "follow_up_questions": payload.get("follow_up_questions", []),
                "used_template": False,
                "photo_url": photo_url,
            }
            _store_response(hass, entry_data, event_type, response)
            return response

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

    if not hass.services.has_service(DOMAIN, SERVICE_BUILD_CONTEXT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_BUILD_CONTEXT,
            handle_build_context,
            schema=BUILD_CONTEXT_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_AUTOMATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_AUTOMATION,
            handle_generate_automation,
            schema=GENERATE_AUTOMATION_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_COMPOSE_NOTIFICATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_COMPOSE_NOTIFICATION,
            handle_compose_notification,
            schema=COMPOSE_NOTIFICATION_SCHEMA,
            supports_response=SupportsResponse.ONLY,
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
    if hass.services.has_service(DOMAIN, SERVICE_BUILD_CONTEXT):
        hass.services.async_remove(DOMAIN, SERVICE_BUILD_CONTEXT)
    if hass.services.has_service(DOMAIN, SERVICE_GENERATE_AUTOMATION):
        hass.services.async_remove(DOMAIN, SERVICE_GENERATE_AUTOMATION)
    if hass.services.has_service(DOMAIN, SERVICE_COMPOSE_NOTIFICATION):
        hass.services.async_remove(DOMAIN, SERVICE_COMPOSE_NOTIFICATION)


def _merge_options(entry: ConfigEntry) -> dict[str, Any]:
    options = {
        CONF_CONTEXT_ENABLED: DEFAULT_CONTEXT_ENABLED,
        CONF_INCLUDE_HISTORY: DEFAULT_INCLUDE_HISTORY,
        CONF_INCLUDE_LOGBOOK: DEFAULT_INCLUDE_LOGBOOK,
        CONF_HISTORY_HOURS: DEFAULT_HISTORY_HOURS,
        CONF_ALLOWLIST_DOMAINS: DEFAULT_ALLOWLIST_DOMAINS,
        CONF_DENYLIST_DOMAINS: DEFAULT_DENYLIST_DOMAINS,
        CONF_ALLOWLIST_ENTITIES: DEFAULT_ALLOWLIST_ENTITIES,
        CONF_DENYLIST_ENTITIES: DEFAULT_DENYLIST_ENTITIES,
        CONF_MAX_CONTEXT_ENTITIES: DEFAULT_MAX_CONTEXT_ENTITIES,
        CONF_SUMMARY_CACHE_TTL: DEFAULT_SUMMARY_CACHE_TTL,
        CONF_INCOGNITO_MODE: DEFAULT_INCOGNITO_MODE,
    }
    options.update(entry.options)
    return options


def _build_context_options(
    base_options: dict[str, Any],
    include_context: bool | None,
    include_history: bool | None,
    include_logbook: bool | None,
    history_hours: int | None,
    focus_areas: list[str] | None,
    focus_entities: list[str] | None,
    recent_mode: bool | None,
    incognito: bool | None,
) -> dict[str, Any]:
    options = dict(base_options)
    options["context_enabled"] = base_options.get(CONF_CONTEXT_ENABLED, True)
    options["incognito"] = base_options.get(CONF_INCOGNITO_MODE, False)
    if include_context is not None:
        options["context_enabled"] = include_context
    if include_history is not None:
        options["include_history"] = include_history
    if include_logbook is not None:
        options["include_logbook"] = include_logbook
    if history_hours is not None:
        options["history_hours"] = history_hours
    if focus_areas:
        options["focus_areas"] = focus_areas
    if focus_entities:
        options["focus_entities"] = focus_entities
    if recent_mode is not None:
        options["recent_mode"] = recent_mode
    if incognito is not None:
        options["incognito"] = incognito
    return options


def _store_response(
    hass: HomeAssistant,
    entry_data: dict[str, Any] | None,
    prompt: str,
    result: dict[str, Any],
) -> None:
    if entry_data and entry_data.get("options", {}).get(CONF_INCOGNITO_MODE):
        return
    response = result.get("message") or result.get("yaml") or ""
    if not response:
        return
    entry = {
        "prompt": prompt,
        "response": response,
        "timestamp": dt_util.utcnow().isoformat(),
    }
    recent = hass.data[DOMAIN].setdefault("recent_responses", [])
    recent.insert(0, entry)
    del recent[10:]


def _get_recent_responses(hass: HomeAssistant, options: dict[str, Any]) -> list[dict[str, Any]]:
    if options.get(CONF_INCOGNITO_MODE):
        return []
    return hass.data[DOMAIN].get("recent_responses", [])


def _iter_agents(hass: HomeAssistant):
    for entry_id, entry_data in hass.data[DOMAIN].items():
        if isinstance(entry_data, dict) and "agent" in entry_data:
            yield entry_id, entry_data
