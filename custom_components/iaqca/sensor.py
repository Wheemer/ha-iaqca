"""Sensor platform to calculate IAQCA index."""

import logging
from collections.abc import Mapping
from typing import Any, Final

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_ENTRY_CONTROLLERS, IaqukController, _get_controller
from .const import (
    DOMAIN,
    ICON_DEFAULT,
    ICON_EXCELLENT,
    ICON_FAIR,
    ICON_GOOD,
    ICON_INADEQUATE,
    ICON_POOR,
    LEVEL_EXCELLENT,
    LEVEL_GOOD,
    LEVEL_INADEQUATE,
    LEVEL_POOR,
    LEVELS,
    SENSOR_INDEX,
    SENSOR_LEVEL,
    SENSORS,
)

_LOGGER: Final = logging.getLogger(__name__)

LEVEL_ICONS: Final = {
    LEVEL_EXCELLENT: ICON_EXCELLENT,
    LEVEL_GOOD: ICON_GOOD,
    LEVEL_POOR: ICON_POOR,
    LEVEL_INADEQUATE: ICON_INADEQUATE,
}


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,  # noqa: ARG001
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up sensors to calculate IAQCA index."""
    if discovery_info is None:
        return

    object_id = discovery_info[CONF_NAME]
    controller = _get_controller(hass, object_id)

    sensors = []
    for sensor_type in discovery_info[CONF_SENSORS]:
        _LOGGER.debug("Initialize sensor %s for controller %s", sensor_type, object_id)
        sensors.append(IaqukSensor(controller, sensor_type))

    async_add_entities(sensors, update_before_add=True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IAQCA sensors from a config entry."""
    entry_data = hass.data[DOMAIN][DATA_ENTRY_CONTROLLERS][entry.entry_id]
    controller = entry_data["controller"]
    async_add_entities(
        [
            IaqukSensor(controller, sensor_type)
            for sensor_type in entry_data[CONF_SENSORS]
        ],
        update_before_add=True,
    )


class IaqukSensor(SensorEntity):
    """IAQCA sensor."""

    def __init__(self, controller: IaqukController, sensor_type: str) -> None:
        """Initialize sensor."""
        self._controller = controller
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{controller.unique_id}_{sensor_type}"
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_translation_key = sensor_type

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._attr_unique_id, hass=controller.hass
        )

        self._attr_name = SENSORS[sensor_type]
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT if sensor_type == SENSOR_INDEX else None
        )
        self._attr_device_class = SensorDeviceClass.AQI
        if sensor_type == SENSOR_LEVEL:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = LEVELS
        self._attr_icon = ICON_DEFAULT if sensor_type == SENSOR_INDEX else ICON_FAIR
        self._attr_device_info = {
            "identifiers": {(DOMAIN, controller.unique_id)},
            "name": controller.name,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self._controller.async_add_listener(self._handle_controller_update)
        )
        self._controller.async_added_to_hass()

    @callback
    def _handle_controller_update(self) -> None:
        """Handle calculated IAQ changes."""
        self.async_schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return self._controller.state_attributes

    async def async_update(self) -> None:
        """Update sensor state."""
        self._attr_available = self._controller.iaq_index is not None
        if self._sensor_type == SENSOR_INDEX:
            self._attr_native_value = self._controller.iaq_index
            return

        level = self._controller.iaq_level
        self._attr_native_value = level
        self._attr_icon = LEVEL_ICONS.get(level, ICON_FAIR)
