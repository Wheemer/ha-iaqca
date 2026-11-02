"""Profile detection and ambiguity regressions across gas sensor families."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iaqca import IaqcaController
from custom_components.iaqca.config_flow import _parse_user_input
from custom_components.iaqca.index_profiles import detect_index_profile


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("sensor.bosch_iaq", "bosch_bsec"),
        ("sensor.sensirion_voc_index", "sensirion_voc"),
        ("sensor.unknown_iaq", None),
        ("sensor.bosch_iaq_accuracy", None),
    ],
)
async def test_automatic_profiles(hass, entity_id, expected):
    """Equal numeric ranges must not imply equal index semantics."""
    hass.states.async_set(entity_id, 160)
    assert detect_index_profile(hass, entity_id) == expected


async def test_unknown_index_requires_scale(hass):
    """Accept an explicit supported scale when metadata is insufficient."""
    hass.states.async_set("sensor.room_iaq", 160, {"unit_of_measurement": "IAQ"})
    form = {"air_quality_index": "sensor.room_iaq"}
    defaults = {"object_id": "test", "name": "Test"}
    _, errors = _parse_user_input(hass, form, defaults)
    assert errors["index_profile"] == "unknown_index_scale"
    data, errors = _parse_user_input(
        hass, {**form, "index_profile": "bosch_bsec"}, defaults
    )
    assert not errors
    assert data["index_profile"] == "bosch_bsec"
    controller = IaqcaController(hass, "test", "Test", form)
    controller.update()
    assert controller.iaq_index is None
    assert (
        controller.state_attributes["source_problems"][0]["reason"]
        == "unknown_index_scale"
    )


@pytest.mark.parametrize(
    ("profile", "points"), [("bosch_bsec", 2), ("sensirion_voc", 3)]
)
async def test_same_value_different_scales(hass, profile, points):
    """Apply each profile's own operational boundaries."""
    hass.states.async_set("sensor.room_iaq", 160)
    controller = IaqcaController(
        hass, "test", "Test", {"air_quality_index": "sensor.room_iaq"}, profile
    )
    controller.update()
    assert controller.state_attributes["air_quality_index_index"] == points
    assert (
        controller.state_attributes["source_values"]["air_quality_index"][0]["profile"]
        == profile
    )


async def test_options_save_profile_and_sources(hass):
    """Configure saves the selected scale and clearing old equivalent sources."""
    hass.states.async_set("sensor.bosch_iaq", 160, {"unit_of_measurement": "IAQ"})
    entry = MockConfigEntry(
        domain="iaqca",
        data={
            "object_id": "room",
            "name": "Room",
            "sensors": ["iaq_level", "iaq_index"],
            "sources": {
                "co2": "sensor.room_co2_equivalent",
                "tvoc": "sensor.room_breath_voc_equivalent",
            },
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Room",
            "air_quality_index": "sensor.bosch_iaq",
            "co2": None,
            "tvoc": None,
            "index_profile": "auto",
            "create_index": True,
        },
    )
    assert result["type"] == "create_entry"
    assert entry.data["sources"] == {"air_quality_index": "sensor.bosch_iaq"}
    assert entry.data["index_profile"] == "auto"
    assert entry.data["object_id"] == "room"
