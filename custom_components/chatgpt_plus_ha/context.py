"""Context builder for ChatGPT Plus HA."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Iterable

from homeassistant.components import history, logbook
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry, device_registry, entity_registry
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALLOWLIST_DOMAINS,
    CONF_ALLOWLIST_ENTITIES,
    CONF_DENYLIST_DOMAINS,
    CONF_DENYLIST_ENTITIES,
    CONF_HISTORY_HOURS,
    CONF_INCLUDE_HISTORY,
    CONF_INCLUDE_LOGBOOK,
    CONF_MAX_CONTEXT_ENTITIES,
    DEFAULT_ALLOWLIST_DOMAINS,
    DEFAULT_ALLOWLIST_ENTITIES,
    DEFAULT_DENYLIST_DOMAINS,
    DEFAULT_DENYLIST_ENTITIES,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_INCLUDE_HISTORY,
    DEFAULT_INCLUDE_LOGBOOK,
    DEFAULT_MAX_CONTEXT_ENTITIES,
)

MAX_LOGBOOK_ENTRIES = 80
MAX_HISTORY_ENTRIES = 150
MAX_LIST_ITEMS = 50
MAX_CONTEXT_CHARS = 6000

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
    re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s_-]", " ", text.lower())


def _tokenize(text: str) -> list[str]:
    normalized = _normalize(text)
    return [token for token in normalized.split() if token]


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)


def _should_redact_name(key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = key.lower()
    if "name" in lowered or "user" in lowered or "owner" in lowered:
        return True
    return False


def _redact_value(value: Any, key: str | None = None) -> Any:
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
        if key and _should_redact_name(key, value):
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
            key: _redact_value(val, key=str(key))
            for key, val in value.items()
            if not _is_sensitive_key(str(key))
        }
    return str(value)


def _serialize_state(state: State, include_attributes: bool) -> dict[str, Any]:
    data = {
        "entity_id": state.entity_id,
        "state": _redact_value(state.state),
        "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        "last_updated": state.last_updated.isoformat() if state.last_updated else None,
    }
    if include_attributes:
        data["attributes"] = _redact_value(state.attributes)
    return data


def _match_score(text: str, tokens: Iterable[str]) -> int:
    if not text:
        return 0
    normalized = _normalize(text)
    return sum(1 for token in tokens if token and token in normalized)


def _trim_summary(summary: str) -> str:
    if len(summary) <= MAX_CONTEXT_CHARS:
        return summary
    return summary[: MAX_CONTEXT_CHARS - 3] + "..."


async def build_context(
    hass: HomeAssistant,
    question: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact, privacy-aware context payload for ChatGPT."""
    options = options or {}
    include_history = bool(
        options.get(CONF_INCLUDE_HISTORY, options.get("include_history", DEFAULT_INCLUDE_HISTORY))
    )
    include_logbook = bool(
        options.get(CONF_INCLUDE_LOGBOOK, options.get("include_logbook", DEFAULT_INCLUDE_LOGBOOK))
    )
    history_hours = int(
        options.get(CONF_HISTORY_HOURS, options.get("history_hours", DEFAULT_HISTORY_HOURS))
    )
    allowlist_domains = set(
        _normalize_list(
            options.get(
                CONF_ALLOWLIST_DOMAINS,
                options.get("allowlist_domains", DEFAULT_ALLOWLIST_DOMAINS),
            )
        )
    )
    denylist_domains = set(
        _normalize_list(
            options.get(
                CONF_DENYLIST_DOMAINS,
                options.get("denylist_domains", DEFAULT_DENYLIST_DOMAINS),
            )
        )
    )
    allowlist_entities = set(
        _normalize_list(
            options.get(
                CONF_ALLOWLIST_ENTITIES,
                options.get("allowlist_entities", DEFAULT_ALLOWLIST_ENTITIES),
            )
        )
    )
    denylist_entities = set(
        _normalize_list(
            options.get(
                CONF_DENYLIST_ENTITIES,
                options.get("denylist_entities", DEFAULT_DENYLIST_ENTITIES),
            )
        )
    )
    max_entities = int(
        options.get(
            CONF_MAX_CONTEXT_ENTITIES,
            options.get("max_entities", DEFAULT_MAX_CONTEXT_ENTITIES),
        )
    )
    include_attributes = bool(options.get("include_attributes", False))
    focus_areas = _normalize_list(options.get("focus_areas", []))
    focus_entities = set(_normalize_list(options.get("focus_entities", [])))
    summary_only = bool(options.get("summary_only", False))
    recent_mode = bool(options.get("recent_mode", False))

    question_tokens = set(_tokenize(question))
    focus_area_tokens = set(_tokenize(" ".join(focus_areas)))

    now = dt_util.utcnow()
    start_time = now - timedelta(hours=history_hours)

    area_reg = area_registry.async_get(hass)
    device_reg = device_registry.async_get(hass)
    entity_reg = entity_registry.async_get(hass)

    area_names = {area.id: area.name for area in area_reg.async_list_areas()}
    device_area = {device.id: device.area_id for device in device_reg.devices.values()}
    device_names = {device.id: device.name for device in device_reg.devices.values()}

    entity_meta: dict[str, dict[str, Any]] = {}
    for entry in entity_reg.entities.values():
        area_id = entry.area_id or device_area.get(entry.device_id)
        entity_meta[entry.entity_id] = {
            "name": entry.name,
            "device_id": entry.device_id,
            "area_id": area_id,
            "area_name": area_names.get(area_id),
            "device_name": device_names.get(entry.device_id),
            "platform": entry.platform,
            "disabled": bool(entry.disabled),
        }

    scored: list[tuple[int, State]] = []
    for state in hass.states.async_all():
        entity_id = state.entity_id
        domain = entity_id.split(".", 1)[0]

        if denylist_domains and domain in denylist_domains:
            continue
        if denylist_entities and entity_id in denylist_entities:
            continue
        if allowlist_domains and domain not in allowlist_domains:
            continue
        if allowlist_entities and entity_id not in allowlist_entities:
            continue

        meta = entity_meta.get(entity_id, {})
        score = 0
        score += 5 if entity_id in focus_entities else 0
        score += _match_score(entity_id, question_tokens) * 2
        score += _match_score(meta.get("name") or "", question_tokens) * 3
        score += _match_score(meta.get("area_name") or "", question_tokens) * 3
        score += _match_score(meta.get("device_name") or "", question_tokens) * 2
        score += _match_score(meta.get("area_name") or "", focus_area_tokens) * 4
        score += _match_score(domain, question_tokens)

        if score > 0:
            scored.append((score, state))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected_states = [state for _, state in scored[:max_entities]]

    if len(selected_states) < max_entities:
        related_states: list[State] = []
        related_area_ids = {
            entity_meta.get(state.entity_id, {}).get("area_id")
            for state in selected_states
        }
        related_area_ids.discard(None)
        if related_area_ids:
            for state in hass.states.async_all():
                if state in selected_states:
                    continue
                meta = entity_meta.get(state.entity_id, {})
                if meta.get("area_id") in related_area_ids:
                    related_states.append(state)
                if len(selected_states) + len(related_states) >= max_entities:
                    break
        selected_states.extend(
            related_states[: max_entities - len(selected_states)]
        )

    summary_lines: list[str] = []
    entity_summaries: list[dict[str, Any]] = []
    for state in selected_states:
        meta = entity_meta.get(state.entity_id, {})
        display_name = meta.get("name") or state.attributes.get("friendly_name") or state.entity_id
        display_name = _redact_value(display_name, key="name")
        summary_lines.append(
            f"- {state.entity_id}: {state.state} ({display_name})"
        )
        entity_summaries.append(_serialize_state(state, include_attributes))

    recent_changes: list[str] = []
    if include_history or recent_mode:
        if "recorder" in hass.config.components:
            try:
                states_by_entity = await hass.async_add_executor_job(
                    history.get_significant_states,
                    hass,
                    start_time,
                    now,
                )
                for entity_id, state_list in states_by_entity.items():
                    if allowlist_entities and entity_id not in allowlist_entities:
                        continue
                    if denylist_entities and entity_id in denylist_entities:
                        continue
                    if allowlist_domains and entity_id.split(".", 1)[0] not in allowlist_domains:
                        continue
                    if denylist_domains and entity_id.split(".", 1)[0] in denylist_domains:
                        continue
                    if not state_list:
                        continue
                    last_state = state_list[-1]
                    recent_changes.append(
                        f"{entity_id} changed to {_redact_value(last_state.state)} at "
                        f"{last_state.last_changed.isoformat() if last_state.last_changed else 'unknown'}"
                    )
                    if len(recent_changes) >= MAX_HISTORY_ENTRIES:
                        break
            except Exception:
                recent_changes = []

    logbook_entries: list[str] = []
    if include_logbook and "logbook" in hass.config.components:
        try:
            events = await logbook.async_get_events(hass, start_time, now)
            for event in events[:MAX_LOGBOOK_ENTRIES]:
                message = _redact_value(event.get("message"), key="message")
                name = _redact_value(event.get("name"), key="name")
                logbook_entries.append(
                    f"{event.get('when') or event.get('time')}: {name} {message}"
                )
        except Exception:
            logbook_entries = []

    summary_parts = []
    if summary_lines:
        summary_parts.append(
            f"Relevant entities ({len(summary_lines)}):\n" + "\n".join(summary_lines)
        )
    if recent_changes:
        summary_parts.append(
            f"Recent changes (last {history_hours}h):\n"
            + "\n".join(recent_changes[:MAX_HISTORY_ENTRIES])
        )

    summary = _trim_summary("\n\n".join(summary_parts))

    if summary_only:
        return {
            "generated_at": now.isoformat(),
            "summary": summary,
            "recent_changes": recent_changes[:MAX_HISTORY_ENTRIES],
        }

    return {
        "generated_at": now.isoformat(),
        "summary": summary,
        "entities": entity_summaries,
        "recent_changes": recent_changes[:MAX_HISTORY_ENTRIES],
        "logbook": logbook_entries[:MAX_LOGBOOK_ENTRIES],
    }
