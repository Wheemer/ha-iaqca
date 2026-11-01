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
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceSelector,
    EntitySelector,
    EntitySelectorConfig,
)
from homeassistant.util import slugify

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
    SENSOR_INDEX,
    SENSOR_LEVEL,
    SENSORS,
)

SOURCE_FIELDS: Final = [*SOURCES]
CONF_CREATE_INDEX: Final = "create_index"
CONF_SOURCE_DEVICE: Final = "source_device"

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
    hass: HomeAssistant,
    user_input: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate form input and return config-entry data plus field errors."""
    defaults = defaults or {}
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
    elif not sensor_ids:
        sensor_ids = [SENSOR_LEVEL]
        if user_input.get(
            CONF_CREATE_INDEX,
            SENSOR_INDEX in defaults.get(CONF_SENSORS, SENSORS),
        ):
            sensor_ids.append(SENSOR_INDEX)

    configured_object_id = user_input.get(CONF_OBJECT_ID) or defaults.get(
        CONF_OBJECT_ID
    )
    if configured_object_id:
        try:
            object_id = cv.slug(configured_object_id)
        except vol.Invalid:
            errors[CONF_OBJECT_ID] = "invalid_object_id"
            object_id = configured_object_id
        generated_name = ""
    else:
        object_id, generated_name = _generate_entry_identity(hass, sources)

    data = {
        CONF_OBJECT_ID: object_id,
        CONF_NAME: user_input.get(CONF_NAME)
        or defaults.get(CONF_NAME)
        or generated_name,
        CONF_SOURCES: sources,
        CONF_SENSORS: sensor_ids,
    }
    return data, errors


def _generate_entry_identity(
    hass: HomeAssistant, sources: dict[str, str | list[str]]
) -> tuple[str, str]:
    """Create a stable internal ID and title without exposing technical fields."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    area_registry = ar.async_get(hass)
    area_name = None
    for source in sources.values():
        entity_id = source[0] if isinstance(source, list) else source
        entity_entry = entity_registry.async_get(entity_id)
        if entity_entry is None:
            continue
        area_id = entity_entry.area_id
        if area_id is None and entity_entry.device_id is not None:
            device_entry = device_registry.async_get(entity_entry.device_id)
            area_id = device_entry.area_id if device_entry is not None else None
        if area_id is not None and (
            area_entry := area_registry.async_get_area(area_id)
        ):
            area_name = area_entry.name
            break

    base = f"{slugify(area_name)}_iaqca" if area_name else "iaqca"
    title = (
        f"{area_name} Canadian Air Quality Index"
        if area_name
        else "Canadian Air Quality Index"
    )
    used_ids = {
        entry.data.get(CONF_OBJECT_ID)
        for entry in hass.config_entries.async_entries(DOMAIN)
    }
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    if suffix > 2:
        title = f"{title} {suffix - 1}"
    return candidate, title


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


def _matches_source(source: str, entity_id: str, device_class: str | None) -> bool:
    """Return whether a sensor is compatible with an IAQ source."""
    if device_classes := SOURCE_DEVICE_CLASSES.get(source):
        return device_class in {item.value for item in device_classes}
    return any(keyword in entity_id.lower() for keyword in SOURCE_KEYWORDS[source])


def _detect_device_sources(
    hass: HomeAssistant, device_id: str
) -> dict[str, str | list[str]]:
    """Discover compatible sensor entities from a device and its area."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    area_id = device_entry.area_id if device_entry is not None else None
    candidates: list[tuple[int, str, str | None]] = []

    for state in hass.states.async_all(SENSOR_DOMAIN):
        registry_entry = entity_registry.async_get(state.entity_id)
        if registry_entry is None:
            continue
        priority = None
        if registry_entry.device_id == device_id:
            priority = 0
        elif area_id is not None:
            entity_area = registry_entry.area_id
            if entity_area is None and registry_entry.device_id is not None:
                entity_device = device_registry.async_get(registry_entry.device_id)
                entity_area = (
                    entity_device.area_id if entity_device is not None else None
                )
            if entity_area == area_id:
                priority = 1
        if priority is not None:
            candidates.append(
                (priority, state.entity_id, state.attributes.get("device_class"))
            )

    candidates.sort()
    sources: dict[str, str | list[str]] = {}
    for source in SOURCE_FIELDS:
        matching = [
            entity_id
            for _, entity_id, device_class in candidates
            if _matches_source(source, entity_id, device_class)
        ]
        if source in SOURCES_LISTS and matching:
            sources[source] = matching
        elif matching:
            sources[source] = matching[0]

    if CONF_TVOC in sources:
        sources.pop(CONF_VOC_INDEX, None)
    return sources


def _device_name(hass: HomeAssistant, device_id: str) -> str:
    """Return a friendly default title for a selected source device."""
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is None:
        return "Canadian Air Quality Index"
    name = device_entry.name_by_user or device_entry.name
    return f"{name} Canadian Air Quality Index"


def _device_schema() -> vol.Schema:
    """Return the first setup step schema."""
    return vol.Schema({vol.Required(CONF_SOURCE_DEVICE): DeviceSelector()})


def _confirm_schema(name: str) -> vol.Schema:
    """Return the short confirmation step schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): str,
            vol.Optional(CONF_CREATE_INDEX, default=True): BooleanSelector(),
        }
    )


def _schema(hass: HomeAssistant, defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the config-flow form schema."""
    defaults = defaults or {}
    default_sources = defaults.get(CONF_SOURCES, {})

    return vol.Schema(
        {
            vol.Optional(
                CONF_CREATE_INDEX,
                default=SENSOR_INDEX in defaults.get(CONF_SENSORS, SENSORS),
            ): BooleanSelector(),
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

        data, errors = _parse_user_input(self.hass, form_input)
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
        """Choose the device used to discover IAQ source sensors."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_SOURCE_DEVICE]
            sources = _detect_device_sources(self.hass, device_id)
            if sources:
                self._source_device_id = device_id
                self._detected_sources = sources
                self._suggested_name = _device_name(self.hass, device_id)
                return await self.async_step_confirm()
            errors["base"] = "no_compatible_sensors"

        return self.async_show_form(
            step_id="user",
            data_schema=_device_schema(),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm generated name and optional numeric sensor."""
        if user_input is not None:
            form_input = {**self._detected_sources, **user_input}
            data, errors = _parse_user_input(self.hass, form_input)
            if not errors:
                data[CONF_SOURCE_DEVICE] = self._source_device_id
                await self.async_set_unique_id(data[CONF_OBJECT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="confirm",
            data_schema=_confirm_schema(self._suggested_name),
            description_placeholders={
                "detected_sources": str(len(self._detected_sources))
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure an existing entry."""
        entry = self._get_reconfigure_entry()
        defaults = {**entry.data, **entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            data, errors = _parse_user_input(self.hass, user_input, defaults)
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
            data, errors = _parse_user_input(self.hass, user_input, defaults)
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
