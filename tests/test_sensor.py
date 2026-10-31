"""Test sensor setup."""

from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import assert_setup_component

from custom_components.iaqca import IaqcaController
from custom_components.iaqca.const import (
    DOMAIN,
    ICON_DEFAULT,
    ICON_EXCELLENT,
    ICON_FAIR,
    ICON_GOOD,
    ICON_INADEQUATE,
    ICON_POOR,
    LEVEL_EXCELLENT,
    LEVEL_FAIR,
    LEVEL_GOOD,
    LEVEL_INADEQUATE,
    LEVEL_POOR,
)
from custom_components.iaqca.sensor import SENSOR_INDEX, SENSOR_LEVEL, IaqcaSensor


async def test_entity_initialization(hass: HomeAssistant):
    """Test sensor initialization."""
    controller = IaqcaController(hass, "test", "Test", {"": "sensor.test_monitored"})
    expected_attributes = {"sources_set": 1, "sources_used": 0}

    entity = IaqcaSensor(controller, SENSOR_INDEX)
    entity.hass = hass

    assert entity.unique_id == "test_iaq_index"
    assert entity.name == "Test Canadian Air Quality Index"
    assert entity.should_poll is True
    assert entity.available is True
    assert entity.device_class == SensorDeviceClass.AQI
    assert entity.state is None
    assert entity.state_class == SensorStateClass.MEASUREMENT
    assert entity.icon == ICON_DEFAULT
    assert entity.unit_of_measurement is None
    assert entity.extra_state_attributes == expected_attributes

    entity = IaqcaSensor(controller, SENSOR_LEVEL)
    entity.hass = hass

    assert entity.unique_id == "test_iaq_level"
    assert entity.name == "Test Canadian Air Quality Level"
    assert entity.should_poll is True
    assert entity.available is True
    assert entity.device_class == "iaqca__level"
    assert entity.state is None
    assert entity.state_class is None
    assert entity.icon == ICON_FAIR
    assert entity.unit_of_measurement is None
    assert entity.extra_state_attributes == expected_attributes

    levels = {
        LEVEL_EXCELLENT: ICON_EXCELLENT,
        LEVEL_GOOD: ICON_GOOD,
        LEVEL_FAIR: ICON_FAIR,
        LEVEL_POOR: ICON_POOR,
        LEVEL_INADEQUATE: ICON_INADEQUATE,
    }

    for lvl, icon in levels.items():
        with patch.object(IaqcaController, "iaq_level", new_callable=lambda: lvl):  # noqa: B023
            controller = IaqcaController(
                hass, "test", "Test", {"": "sensor.test_monitored"}
            )
            entity = IaqcaSensor(controller, SENSOR_LEVEL)
            entity.hass = hass
            await entity.async_update()

            assert entity.state == lvl
            assert entity.icon == icon


async def test_async_setup_platform(hass: HomeAssistant):
    """Test platform setup."""
    with assert_setup_component(1, "sensor"):
        await async_setup_component(hass, "sensor", {"sensor": {"platform": DOMAIN}})
        await hass.async_block_till_done()
