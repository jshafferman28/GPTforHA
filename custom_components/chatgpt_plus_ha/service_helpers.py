"""Helper utilities for ChatGPT Plus HA services."""

from __future__ import annotations

import json
import re
from typing import Any

from homeassistant.util.yaml import parse_yaml

EVENT_TEMPLATES = {
    "garage_open": {
        "title": "Garage door left open",
        "message": "The garage door appears to be open. Would you like to close it?",
        "actions": ["Close garage", "Remind me in 10 minutes", "Ignore"],
        "questions": ["Is anyone working in the garage?"],
    },
    "leak_detected": {
        "title": "Leak detected",
        "message": "A leak sensor reported water detected. Consider shutting off water and checking the area.",
        "actions": ["Shut off water", "View sensors", "Call for help"],
        "questions": ["Where is the leak sensor located?"],
    },
    "motion_at_night": {
        "title": "Motion detected at night",
        "message": "Motion was detected during quiet hours. Do you want to turn on lights or check cameras?",
        "actions": ["Turn on lights", "View cameras", "Ignore"],
        "questions": ["Is this expected activity?"],
    },
    "hvac_anomaly": {
        "title": "HVAC anomaly detected",
        "message": "HVAC behavior looks unusual. Check filters or adjust setpoints if needed.",
        "actions": ["Check thermostat", "Adjust setpoint", "Ignore"],
        "questions": ["Is the home occupied right now?"],
    },
}


def extract_json_payload(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    payload = text[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def validate_automation_yaml(yaml_text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    config: dict[str, Any] | None = None

    try:
        parsed = parse_yaml(yaml_text)
    except Exception as err:
        return {"valid": False, "errors": [str(err)], "warnings": [], "config": None}

    if not isinstance(parsed, dict):
        errors.append("Automation YAML must be a single mapping (not a list).")
        return {"valid": False, "errors": errors, "warnings": warnings, "config": None}

    config = parsed

    for required in ("trigger", "action"):
        if required not in config:
            errors.append(f"Missing required '{required}' section.")

    trigger = config.get("trigger")
    if trigger is not None and not isinstance(trigger, (list, dict)):
        errors.append("Trigger must be a list or mapping.")

    action = config.get("action")
    if action is not None and not isinstance(action, (list, dict)):
        errors.append("Action must be a list or mapping.")

    if "mode" not in config:
        warnings.append("Consider adding 'mode' to control automation behavior.")

    if _has_potential_loop(action):
        warnings.append("Action references automation services; verify this won't loop.")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "config": config}


def _has_potential_loop(action: Any) -> bool:
    actions = _flatten_actions(action)
    for item in actions:
        service = str(item.get("service", ""))
        if service.startswith("automation."):
            return True
    return False


def _flatten_actions(action: Any) -> list[dict[str, Any]]:
    if action is None:
        return []
    if isinstance(action, dict):
        return [action]
    if isinstance(action, list):
        return [item for item in action if isinstance(item, dict)]
    return []


def build_notification_template(event_type: str) -> dict[str, Any] | None:
    key = re.sub(r"[^a-z0-9_]", "_", event_type.lower()).strip("_")
    return EVENT_TEMPLATES.get(key)
