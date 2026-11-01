"""Config flow for Canadian Air Quality Index."""

from __future__ import annotations

from typing import Any, Final

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import CONF_NAME, CONF_SENSORS
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from . import SOURCES, SOURCES_LISTS, check_voc_keys
from .const import (
    CONF_CO,
    CONF_CO2,
    CONF_HCHO,
    CONF_HUMIDITY,
    CONF_NO2,
    CONF_OBJECT_ID,
    CONF_PM,
    CONF_RADON,
    CONF_SOURCES,
    CONF_TEMPERATURE,
    CONF_TVOC,
    CONF_VOC_INDEX,
    DOMAIN,
    SENSORS,
)

SOURCE_FIELDS: Final = [*SOURCES]

SOURCE_DEVICE_CLASSES: Final = {
    CONF_TEMPERATURE: [SensorDeviceClass.TEMPERATURE],
    CONF_HUMIDITY: [SensorDeviceClass.HUMIDITY],
    CONF_CO2: [SensorDeviceClass.CO2],
    CONF_CO: [SensorDeviceClass.CO],
    CONF_NO2: [SensorDeviceClass.NITROGEN_DIOXIDE],
    CONF_TVOC: [
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    ],
    CONF_RADON: [SensorDeviceClass.RADON],
    CONF_PM: [
        SensorDeviceClass.PM1,
        SensorDeviceClass.PM25,
        SensorDeviceClass.PM10,
        SensorDeviceClass.PM4,
    ],
}

# Home Assistant does not define device classes for formaldehyde or VOC index.
# Restrict those selectors to entities whose ID or name explicitly identifies them.
SOURCE_KEYWORDS: Final = {
    CONF_VOC_INDEX: ("voc_index", "voc index"),
    CONF_HCHO: ("hcho", "formaldehyde"),
}


def _csv(value: str | list[str] | None) -> list[str]:
    """Return a clean list from comma-separated or list input."""
    if value is None:
        return []
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_user_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate form input and return config-entry data plus field errors."""
    errors: dict[str, str] = {}
    sources: dict[str, str | list[str]] = {}

    for source in SOURCE_FIELDS:
        raw_value = user_input.get(source)
        if not raw_value:
            continue

        try:
            if source in SOURCES_LISTS:
                sources[source] = cv.entity_ids(raw_value)
            else:
                sources[source] = cv.entity_id(raw_value)
        except vol.Invalid:
            errors[source] = "invalid_entity"

    try:
        cv.has_at_least_one_key(*SOURCES)(sources)
        check_voc_keys(sources)
    except vol.Invalid as err:
        errors["base"] = "invalid_sources" if str(err) else "missing_sources"

    sensor_ids = _csv(user_input.get(CONF_SENSORS))
    invalid_sensors = [sensor for sensor in sensor_ids if sensor not in SENSORS]
    if invalid_sensors:
        errors[CONF_SENSORS] = "invalid_sensor"
    if not sensor_ids:
        sensor_ids = list(SENSORS)

    try:
        object_id = cv.slug(user_input[CONF_OBJECT_ID])
    except vol.Invalid:
        errors[CONF_OBJECT_ID] = "invalid_object_id"
        object_id = user_input.get(CONF_OBJECT_ID, "")

    data = {
        CONF_OBJECT_ID: object_id,
        CONF_NAME: user_input.get(CONF_NAME) or object_id.replace("_", " ").title(),
        CONF_SOURCES: sources,
        CONF_SENSORS: sensor_ids,
    }
    return data, errors


def _source_selector(hass: HomeAssistant, source: str) -> EntitySelector:
    """Build an entity selector containing only compatible IAQ sources."""
    config: EntitySelectorConfig = {
        "multiple": source in SOURCES_LISTS,
        "reorder": source in SOURCES_LISTS,
    }

    if device_classes := SOURCE_DEVICE_CLASSES.get(source):
        config["filter"] = {
            "domain": SENSOR_DOMAIN,
            "device_class": [device_class.value for device_class in device_classes],
        }
    else:
        keywords = SOURCE_KEYWORDS[source]
        config["include_entities"] = [
            state.entity_id
            for state in hass.states.async_all(SENSOR_DOMAIN)
            if any(
                keyword in f"{state.entity_id} {state.name}".lower()
                for keyword in keywords
            )
        ]

    return EntitySelector(config)


def _schema(hass: HomeAssistant, defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the config-flow form schema."""
    defaults = defaults or {}
    default_sources = defaults.get(CONF_SOURCES, {})

    return vol.Schema(
        {
            vol.Required(CONF_OBJECT_ID, default=defaults.get(CONF_OBJECT_ID, "")): str,
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
            vol.Optional(
                CONF_SENSORS,
                default=(
                    defaults.get(CONF_SENSORS, "")
                    if isinstance(defaults.get(CONF_SENSORS), str)
                    else ", ".join(defaults.get(CONF_SENSORS, SENSORS))
                ),
            ): str,
            **{
                vol.Optional(
                    source,
                    default=default_sources.get(
                        source, [] if source in SOURCES_LISTS else ""
                    ),
                ): _source_selector(hass, source)
                for source in SOURCE_FIELDS
            },
        }
    )


class IaqcaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an IAQCA config flow."""

    VERSION = 2

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import legacy YAML configuration into a config entry."""
        if CONF_SOURCES in user_input:
            form_input = {
                **user_input[CONF_SOURCES],
                CONF_OBJECT_ID: user_input[CONF_OBJECT_ID],
                CONF_NAME: user_input.get(CONF_NAME),
                CONF_SENSORS: user_input.get(CONF_SENSORS),
            }
        else:
            form_input = user_input

        data, errors = _parse_user_input(form_input)
        if errors:
            return self.async_abort(reason="invalid_sources")

        await self.async_set_unique_id(data[CONF_OBJECT_ID])
        for entry in self._async_current_entries():
            if (
                entry.unique_id == data[CONF_OBJECT_ID]
                or entry.data.get(CONF_OBJECT_ID) == data[CONF_OBJECT_ID]
            ):
                self.hass.config_entries.async_update_entry(
                    entry, title=data[CONF_NAME], data=data, options={}
                )
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(title=data[CONF_NAME], data=data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _parse_user_input(user_input)
            if not errors:
                await self.async_set_unique_id(data[CONF_OBJECT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure an existing entry."""
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, **entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _parse_user_input(user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry, title=data[CONF_NAME], data=data, options={}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(self.hass, user_input or defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IaqcaOptionsFlow:
        """Create the options flow."""
        return IaqcaOptionsFlow(config_entry)


class IaqcaOptionsFlow(config_entries.OptionsFlow):
    """Handle IAQCA options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage IAQCA options."""
        defaults = {**self._config_entry.data, **self._config_entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _parse_user_input(user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    title=data[CONF_NAME],
                    data=data,
                    options={},
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.hass, user_input or defaults),
            errors=errors,
        )
