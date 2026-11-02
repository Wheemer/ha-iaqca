"""Bosch BSEC scale and gas-source selection regressions."""

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers import device_registry as dr, entity_registry as er
from voluptuous import Invalid
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.iaqca import IaqcaController, check_voc_keys
from custom_components.iaqca.config_flow import (
    _detect_device_sources,
    _parse_user_input,
    _source_selector,
)


@pytest.mark.parametrize(
    ("value", "points"),
    [
        (0, 5),
        (50, 5),
        (50.1, 4),
        (100, 4),
        (100.1, 3),
        (150, 3),
        (150.1, 2),
        (200, 2),
        (200.1, 1),
        (500, 1),
    ],
)
async def test_bsec_boundaries(hass, value, points):
    """Use Bosch bands rather than the existing generic VOC-index bands."""
    hass.states.async_set("sensor.bosch_iaq", value, {"unit_of_measurement": "IAQ"})
    controller = IaqcaController(
        hass, "test", "Test", {"air_quality_index": "sensor.bosch_iaq"}
    )
    controller.update()
    assert controller.state_attributes["air_quality_index_index"] == points
    assert controller.iaq_index == points * 13


@pytest.mark.parametrize("value", [-1, 501, "nan", "inf", "unknown", "unavailable"])
async def test_bsec_invalid_values(hass, value):
    """Reject invalid readings instead of producing an excellent score."""
    hass.states.async_set("sensor.bosch_iaq", value, {"unit_of_measurement": "IAQ"})
    controller = IaqcaController(
        hass, "test", "Test", {"air_quality_index": "sensor.bosch_iaq"}
    )
    assert controller._air_quality_index_index is None
    assert controller._source_problems


async def test_bsec_rejects_concentrations(hass):
    """A ppm concentration is not a Bosch IAQ index."""
    hass.states.async_set("sensor.bosch_iaq", 5, {"unit_of_measurement": "ppm"})
    controller = IaqcaController(
        hass, "test", "Test", {"air_quality_index": "sensor.bosch_iaq"}, "bosch_bsec"
    )
    assert controller._air_quality_index_index is None
    assert controller._source_problems[0]["reason"] == "invalid_unit"


@pytest.mark.parametrize("other", ["tvoc", "voc_index"])
def test_bsec_mutually_exclusive(other):
    """Do not count the same gas signal through multiple source formats."""
    with pytest.raises(Invalid):
        check_voc_keys({"air_quality_index": "sensor.iaq", other: "sensor.voc"})


async def test_equivalent_sources_accepted(hass):
    """Equivalent estimates stay selectable and save without validation blocks."""
    hass.states.async_set("sensor.co2_equivalent", 1500)
    hass.states.async_set("sensor.breath_voc_equivalent", 4.8)
    _, errors = _parse_user_input(
        hass,
        {
            "co2": "sensor.co2_equivalent",
            "tvoc": "sensor.breath_voc_equivalent",
        },
        {"object_id": "test", "name": "Test"},
    )
    assert not errors


@pytest.mark.parametrize("native_state", [160, "unavailable"])
async def test_bsec_discovery(hass, native_state):
    """Keep estimates discoverable and score correlated outputs once."""
    config_entry = MockConfigEntry(domain="esphome")
    config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("esphome", "spikes")},
        name="Spikes",
    )
    registry = er.async_get(hass)
    sensors = [
        ("iaq", "IAQ", None),
        ("co2_equivalent", "ppm", SensorDeviceClass.CO2),
        (
            "breath_voc_equivalent",
            "ppm",
            SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        ),
        ("temperature", "°C", SensorDeviceClass.TEMPERATURE),
        ("humidity", "%", SensorDeviceClass.HUMIDITY),
    ]
    for name, unit, device_class in sensors:
        entry = registry.async_get_or_create(
            "sensor",
            "esphome",
            name,
            suggested_object_id=f"spikes_{name}",
            device_id=device.id,
        )
        hass.states.async_set(
            entry.entity_id,
            50,
            {
                "unit_of_measurement": unit,
                "device_class": device_class,
            },
        )
    assert _detect_device_sources(hass, device.id) == {
        "co2": "sensor.spikes_co2_equivalent",
        "tvoc": "sensor.spikes_breath_voc_equivalent",
        "temperature": "sensor.spikes_temperature",
        "humidity": "sensor.spikes_humidity",
    }
    selector = _source_selector(hass, "tvoc")
    assert not selector.config.get("exclude_entities")
    assert (
        "sensor.spikes_iaq"
        in _source_selector(hass, "air_quality_index").config["include_entities"]
    )
    for name, value in {
        "iaq": native_state,
        "co2_equivalent": 1500,
        "breath_voc_equivalent": 4.8,
        "temperature": 20,
        "humidity": 50,
    }.items():
        entity_id = f"sensor.spikes_{name}"
        hass.states.async_set(
            entity_id, value, dict(hass.states.get(entity_id).attributes)
        )
    controller = IaqcaController(
        hass, "test", "Test", _detect_device_sources(hass, device.id)
    )
    controller.update()
    summary = controller.state_attributes["calculation_summary"]
    assert summary["sources_used"] == 4
    assert summary["scoring_contributions"] == 3
    assert controller.iaq_index == (52 if native_state == 160 else 47)
    reading = controller.state_attributes["source_values"]["tvoc"][0]
    assert reading["estimated"] is True
    assert reading["selected_entity_id"] == "sensor.spikes_breath_voc_equivalent"
    assert reading["entity_id"] == "sensor.spikes_breath_voc_equivalent"
    if native_state == 160:
        assert reading["scoring_entity_id"] == "sensor.spikes_iaq"
        assert reading["scoring_value"] == 160
    assert reading["scoring_method"] == (
        "native_index" if native_state == 160 else "concentration_proxy"
    )

    hass.states.async_set("sensor.actual_co2", 1400, {"unit_of_measurement": "ppm"})
    measured = IaqcaController(
        hass,
        "measured",
        "Measured",
        {
            "co2": "sensor.actual_co2",
            "tvoc": "sensor.spikes_breath_voc_equivalent",
        },
    )
    measured.update()
    assert (
        measured.state_attributes["calculation_summary"]["scoring_contributions"] == 2
    )
    assert (
        measured.state_attributes["source_values"]["co2"][0]["entity_id"]
        == "sensor.actual_co2"
    )

    if native_state == 160:
        controller.async_added_to_hass()
        hass.states.async_set("sensor.spikes_iaq", 50, {"unit_of_measurement": "IAQ"})
        await hass.async_block_till_done()
        assert controller.iaq_index == 65
        controller.async_shutdown()
