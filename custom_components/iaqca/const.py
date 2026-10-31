"""Constants for calculating IAQCA index."""

from typing import Final

from homeassistant.components.sensor import DOMAIN as SENSOR

# Base component constants
NAME: Final = "Indoor Air Quality Canada Index"
DOMAIN: Final = "iaqca"
OLD_DOMAIN: Final = "iaquk"
VERSION: Final = "1.8.0"
ISSUE_URL: Final = "https://github.com/Wheemer/ha-iaqca/issues"

STARTUP_MESSAGE: Final = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have ANY issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

# Icons
ICON_DEFAULT: Final = "mdi:air-filter"
ICON_EXCELLENT: Final = "mdi:emoticon-excited"
ICON_GOOD: Final = "mdi:emoticon-happy"
ICON_FAIR: Final = "mdi:emoticon-neutral"
ICON_POOR: Final = "mdi:emoticon-sad"
ICON_INADEQUATE: Final = "mdi:emoticon-dead"

# Device classes
BINARY_SENSOR_DEVICE_CLASS: Final = "connectivity"

# Platforms
PLATFORMS: Final = [SENSOR]

SENSOR_INDEX: Final = "iaq_index"
SENSOR_LEVEL: Final = "iaq_level"

SENSORS: Final = {
    SENSOR_INDEX: "Indoor Air Quality Index",
    SENSOR_LEVEL: "Indoor Air Quality Level",
}

# Configuration and options
CONF_SOURCES: Final = "sources"
CONF_OBJECT_ID: Final = "object_id"
CONF_TEMPERATURE: Final = "temperature"
CONF_HUMIDITY: Final = "humidity"
CONF_CO2: Final = "co2"
CONF_TVOC: Final = "tvoc"
CONF_VOC_INDEX: Final = "voc_index"
CONF_PM: Final = "pm"
CONF_NO2: Final = "no2"
CONF_CO: Final = "co"
CONF_HCHO: Final = "hcho"  # Formaldehyde
CONF_RADON: Final = "radon"

# Attributes
ATTR_ADVISORY_STATUS: Final = "advisory_status"
ATTR_ACTIVE_ISSUES: Final = "active_issues"
ATTR_ADVISORY_PROFILE: Final = "advisory_profile"
ATTR_AVAILABLE_SOURCES: Final = "available_sources"
ATTR_CALCULATION_SUMMARY: Final = "calculation_summary"
ATTR_SCORING_PROFILE: Final = "scoring_profile"
ATTR_SOURCE_PROBLEMS: Final = "source_problems"
ATTR_SOURCE_SUMMARY: Final = "source_summary"
ATTR_SOURCES_SET: Final = "sources_set"
ATTR_SOURCES_USED: Final = "sources_used"
ATTR_UNAVAILABLE_SOURCES: Final = "unavailable_sources"
ATTR_SOURCE_INDEX_TPL: Final = "{}_index"
ATTR_SOURCE_STATUS: Final = "source_status"
ATTR_SOURCE_VALUES: Final = "source_values"
ATTR_WORST_SOURCES: Final = "worst_sources"
ATTR_WORST_SOURCE_INDEX: Final = "worst_source_index"


LEVEL_EXCELLENT: Final = "Excellent"
LEVEL_GOOD: Final = "Good"
LEVEL_FAIR: Final = "Fair"
LEVEL_POOR: Final = "Poor"
LEVEL_INADEQUATE: Final = "Inadequate"

LEVELS: Final = [
    LEVEL_INADEQUATE,
    LEVEL_POOR,
    LEVEL_FAIR,
    LEVEL_GOOD,
    LEVEL_EXCELLENT,
]

UNIT_PPM: Final = {
    "ppm": 1,  # Target unit -- conversion rate will be ignored
    "ppb": 0.001,
}
UNIT_PPB: Final = {
    "ppb": 1,  # Target unit -- conversion rate will be ignored
    "ppm": 1000,
}
UNIT_UGM3: Final = {
    "µg/m³": 1,  # Target unit -- conversion rate will be ignored
    "μg/m³": 1,  # Add this: Greek Small Letter Mu (\u03bc)
    "µg/m3": 1,
    "µg/m^3": 1,
    "ug/m³": 1,
    "ug/m3": 1,
    "ug/m^3": 1,
    "mg/m³": 1000,
    "mg/m3": 1000,
    "mg/m^3": 1000,
}
UNIT_MGM3: Final = {
    "mg/m³": 1,  # Target unit -- conversion rate will be ignored
    "mg/m3": 1,
    "mg/m^3": 1,
    "µg/m³": 0.001,
    "µg/m3": 0.001,
    "µg/m^3": 0.001,
    "ug/m³": 0.001,
    "ug/m3": 0.001,
    "ug/m^3": 0.001,
}

MWEIGTH_TVOC: Final = 78.9516  # g/mol
MWEIGTH_HCHO: Final = 30.0260  # g/mol
MWEIGTH_CO: Final = 28.0100  # g/mol
MWEIGTH_NO2: Final = 46.0100  # g/mol
MWEIGTH_CO2: Final = 44.0100  # g/mol
