"""Context builder for ChatGPT Plus HA."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from homeassistant.components import history, logbook
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry, device_registry, entity_registry
from homeassistant.util import dt as dt_util

MAX_LOGBOOK_ENTRIES = 100
MAX_HISTORY_ENTRIES = 200
MAX_LIST_ITEMS = 50

SENSITIVE_KEYS = (
    "token",
    "access_token",
    "refresh_token",
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "credential",
    "cookie",
    "jwt",
    "bearer",
    "client_secret",
)

SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"^sk-[A-Za-z0-9]{20,}$"),
    re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"),
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)


def _redact_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in ("bearer ", "token", "password", "secret", "apikey", "api_key")):
            return "[redacted]"
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.match(value):
                return "[redacted]"
        if len(value) > 40 and re.fullmatch(r"[A-Za-z0-9._=-]+", value):
            return "[redacted]"
        return value
    if isinstance(value, list):
        trimmed = value[:MAX_LIST_ITEMS]
        return [_redact_value(item) for item in trimmed]
    if isinstance(value, tuple):
        trimmed = list(value)[:MAX_LIST_ITEMS]
        return [_redact_value(item) for item in trimmed]
    if isinstance(value, dict):
        return {
            key: _redact_value(val)
            for key, val in value.items()
            if not _is_sensitive_key(str(key))
        }
    return str(value)


def _serialize_state(state: State) -> dict[str, Any]:
    return {
        "entity_id": state.entity_id,
        "state": _redact_value(state.state),
        "attributes": _redact_value(state.attributes),
        "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        "last_updated": state.last_updated.isoformat() if state.last_updated else None,
    }


async def build_context(hass: HomeAssistant, window_minutes: int) -> dict[str, Any]:
    """Build a context payload for ChatGPT."""
    now = dt_util.utcnow()
    start_time = now - timedelta(minutes=window_minutes)

    states = [_serialize_state(state) for state in hass.states.async_all()]

    area_reg = area_registry.async_get(hass)
    device_reg = device_registry.async_get(hass)
    entity_reg = entity_registry.async_get(hass)

    areas = [
        {
            "id": area.id,
            "name": area.name,
        }
        for area in area_reg.async_list_areas()
    ]

    devices = []
    for device in device_reg.devices.values():
        devices.append(
            {
                "id": device.id,
                "name": device.name,
                "area_id": device.area_id,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "sw_version": device.sw_version,
                "hw_version": device.hw_version,
                "entry_type": str(device.entry_type) if device.entry_type else None,
                "via_device_id": device.via_device_id,
            }
        )

    entities = []
    for entity in entity_reg.entities.values():
        entities.append(
            {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "device_id": entity.device_id,
                "area_id": entity.area_id,
                "platform": entity.platform,
                "disabled": bool(entity.disabled),
            }
        )

    logbook_entries: list[dict[str, Any]] = []
    if "logbook" in hass.config.components:
        try:
            events = await logbook.async_get_events(hass, start_time, now)
            for event in events[:MAX_LOGBOOK_ENTRIES]:
                logbook_entries.append(
                    {
                        "when": event.get("when") or event.get("time"),
                        "name": event.get("name"),
                        "message": _redact_value(event.get("message")),
                        "entity_id": event.get("entity_id"),
                        "domain": event.get("domain"),
                    }
                )
        except Exception:
            logbook_entries = []

    history_entries: list[dict[str, Any]] = []
    if "recorder" in hass.config.components:
        try:
            states_by_entity = await hass.async_add_executor_job(
                history.get_significant_states,
                hass,
                start_time,
                now,
            )
            for entity_id, state_list in states_by_entity.items():
                for item in state_list:
                    history_entries.append(
                        {
                            "entity_id": entity_id,
                            "state": _redact_value(item.state),
                            "last_changed": item.last_changed.isoformat()
                            if item.last_changed
                            else None,
                        }
                    )
                    if len(history_entries) >= MAX_HISTORY_ENTRIES:
                        break
                if len(history_entries) >= MAX_HISTORY_ENTRIES:
                    break
        except Exception:
            history_entries = []

    return {
        "generated_at": now.isoformat(),
        "window_minutes": window_minutes,
        "entities_state": states,
        "areas": areas,
        "devices": devices,
        "entities": entities,
        "logbook": logbook_entries,
        "history": history_entries,
    }
