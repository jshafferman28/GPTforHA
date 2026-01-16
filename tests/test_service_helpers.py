from custom_components.chatgpt_plus_ha.service_helpers import (
    build_notification_template,
    extract_json_payload,
    validate_automation_yaml,
)


def test_extract_json_payload():
    text = "Here is your result: {\"yaml\": \"alias: Test\"}"
    payload = extract_json_payload(text)
    assert payload is not None
    assert payload["yaml"] == "alias: Test"


def test_validate_automation_yaml_valid():
    yaml_text = """
alias: Test Automation
trigger:
  - platform: state
    entity_id: light.kitchen
    to: "on"
action:
  - service: light.turn_off
    target:
      entity_id: light.kitchen
"""
    result = validate_automation_yaml(yaml_text)
    assert result["valid"] is True


def test_validate_automation_yaml_missing_action():
    yaml_text = """
alias: Broken Automation
trigger:
  - platform: state
    entity_id: light.kitchen
"""
    result = validate_automation_yaml(yaml_text)
    assert result["valid"] is False
    assert any("action" in err for err in result["errors"])


def test_build_notification_template():
    template = build_notification_template("garage_open")
    assert template is not None
    assert "Garage" in template["title"]
