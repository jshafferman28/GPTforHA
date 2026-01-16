import pytest

from homeassistant.core import State

from custom_components.chatgpt_plus_ha import context as ctx


class FakeStates:
    def __init__(self, states):
        self._states = states

    def async_all(self):
        return list(self._states)


class FakeConfig:
    def __init__(self, components=None):
        self.components = components or set()


class FakeHass:
    def __init__(self, states):
        self.states = FakeStates(states)
        self.config = FakeConfig()

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)


class FakeArea:
    def __init__(self, area_id, name):
        self.id = area_id
        self.name = name


class FakeAreaRegistry:
    def async_list_areas(self):
        return [FakeArea("kitchen", "Kitchen")]


class FakeDevice:
    def __init__(self, device_id, name, area_id):
        self.id = device_id
        self.name = name
        self.area_id = area_id


class FakeDeviceRegistry:
    def __init__(self):
        self.devices = {"dev1": FakeDevice("dev1", "Kitchen Device", "kitchen")}


class FakeEntityEntry:
    def __init__(self, entity_id, name, device_id, area_id, platform="light"):
        self.entity_id = entity_id
        self.name = name
        self.device_id = device_id
        self.area_id = area_id
        self.platform = platform
        self.disabled = False


class FakeEntityRegistry:
    def __init__(self):
        self.entities = {
            "light.kitchen": FakeEntityEntry(
                "light.kitchen",
                "Kitchen Light",
                "dev1",
                "kitchen",
            )
        }


@pytest.mark.asyncio
async def test_build_context_selects_relevant_entity(monkeypatch):
    monkeypatch.setattr(ctx.area_registry, "async_get", lambda hass: FakeAreaRegistry())
    monkeypatch.setattr(ctx.device_registry, "async_get", lambda hass: FakeDeviceRegistry())
    monkeypatch.setattr(ctx.entity_registry, "async_get", lambda hass: FakeEntityRegistry())

    states = [
        State("light.kitchen", "on", {"friendly_name": "Kitchen Light"}),
        State("sensor.outdoor_temp", "72", {"friendly_name": "Outdoor Temp"}),
    ]
    hass = FakeHass(states)

    result = await ctx.build_context(
        hass,
        "kitchen light status",
        {"include_history": False, "include_logbook": False},
    )

    assert "light.kitchen" in result["summary"]


def test_redact_value_masks_tokens():
    assert ctx._redact_value("sk-testtoken1234567890") == "[redacted]"
    assert ctx._redact_value("user@example.com") == "[redacted]"
