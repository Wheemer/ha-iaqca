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


async def test_equivalent_sources_rejected(hass):
    """Tell users to choose the Bosch index instead of equivalent estimates."""
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
    assert errors["co2"] == "equivalent_source"
    assert errors["tvoc"] == "equivalent_source"


async def test_bsec_discovery(hass):
    """Detect Spike-like BSEC sources without selecting derived gas estimates."""
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
        "air_quality_index": "sensor.spikes_iaq",
        "temperature": "sensor.spikes_temperature",
        "humidity": "sensor.spikes_humidity",
    }
    selector = _source_selector(hass, "tvoc")
    assert "sensor.spikes_breath_voc_equivalent" in selector.config["exclude_entities"]
    assert (
        "sensor.spikes_iaq"
        in _source_selector(hass, "air_quality_index").config["include_entities"]
    )
