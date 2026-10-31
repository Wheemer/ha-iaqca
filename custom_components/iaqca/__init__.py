"""
Component to calculate IAQCA index.

For more details about this component, please refer to
https://github.com/Wheemer/ha-iaqca
"""

import logging
from collections.abc import Callable
from typing import Any, Final

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_SENSORS,
    EVENT_HOMEASSISTANT_STARTED,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    UnitOfTemperature,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    ATTR_ACTIVE_ISSUES,
    ATTR_ADVISORY_STATUS,
    ATTR_ADVISORY_PROFILE,
    ATTR_AVAILABLE_SOURCES,
    ATTR_CALCULATION_SUMMARY,
    ATTR_SCORING_PROFILE,
    ATTR_SOURCE_INDEX_TPL,
    ATTR_SOURCE_PROBLEMS,
    ATTR_SOURCE_STATUS,
    ATTR_SOURCE_SUMMARY,
    ATTR_SOURCE_VALUES,
    ATTR_SOURCES_SET,
    ATTR_SOURCES_USED,
    ATTR_UNAVAILABLE_SOURCES,
    ATTR_WORST_SOURCE_INDEX,
    ATTR_WORST_SOURCES,
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
    LEGACY_DOMAIN,
    LEVEL_EXCELLENT,
    LEVEL_FAIR,
    LEVEL_GOOD,
    LEVEL_INADEQUATE,
    LEVEL_POOR,
    MWEIGTH_CO,
    MWEIGTH_CO2,
    MWEIGTH_HCHO,
    MWEIGTH_NO2,
    MWEIGTH_TVOC,
    SENSORS,
    STARTUP_MESSAGE,
    UNIT_MGM3,
    UNIT_PPM,
    UNIT_UGM3,
)

_LOGGER: Final = logging.getLogger(__name__)

DATA_CONTROLLERS: Final = "controllers"
DATA_ENTRY_CONTROLLERS: Final = "entry_controllers"
ADVISORY_PROFILE: Final = "simple_canadian_guidance_with_operational_signals"
SCORING_PROFILE: Final = "iaqca_simple_canadian_guidance_1_to_65"
STATUS_SEVERITY: Final = {
    "good": 0,
    "acceptable": 1,
    "out_of_range": 2,
    "elevated": 3,
    "high": 4,
}


def check_voc_keys(conf: ConfigType) -> ConfigType:
    """Ensure CONF_TVOC, CONF_VOC_INDEX or none of them are provided."""
    keys: Final = [CONF_TVOC, CONF_VOC_INDEX]
    count = sum(param in conf for param in keys)
    if count > 1:
        raise vol.Invalid(
            "You must provide none or only one of the following: , ".join(keys)
        )
    return conf


SOURCES: Final = [
    CONF_TEMPERATURE,
    CONF_HUMIDITY,
    CONF_CO2,
    CONF_CO,
    CONF_NO2,
    CONF_TVOC,
    CONF_VOC_INDEX,
    CONF_HCHO,
    CONF_RADON,
    CONF_PM,
]

SOURCES_LISTS: Final = [CONF_CO, CONF_PM]

SOURCES_SCHEMA: Final = vol.All(
    vol.Schema(
        {
            vol.Optional(src): (cv.entity_ids if src in SOURCES_LISTS else cv.entity_id)
            for src in SOURCES
        }
    ),
    cv.has_at_least_one_key(*SOURCES),
    check_voc_keys,
)

IAQ_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCES): SOURCES_SCHEMA,
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
    }
)

CONFIG_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(DOMAIN): cv.schema_with_slug_keys(IAQ_SCHEMA),
        vol.Optional(LEGACY_DOMAIN): cv.schema_with_slug_keys(IAQ_SCHEMA),
    },
    extra=vol.ALLOW_EXTRA,
)


def _deslugify(string: str) -> str:
    """Deslugify string."""
    return string.replace("_", " ").title()


def _ensure_domain_data(hass: HomeAssistant) -> dict[str, Any]:
    """Return integration runtime data."""
    data = hass.data.setdefault(DOMAIN, {})
    data.setdefault(DATA_CONTROLLERS, {})
    data.setdefault(DATA_ENTRY_CONTROLLERS, {})
    return data


def _get_controller(hass: HomeAssistant, object_id: str) -> "IaqcaController":
    """Return a configured controller by object id."""
    data = _ensure_domain_data(hass)
    return data[DATA_CONTROLLERS][object_id]


def _configured_entry_object_ids(hass: HomeAssistant) -> set[str]:
    """Return IAQ object IDs already backed by config entries."""
    return {
        entry.data.get(CONF_OBJECT_ID)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_OBJECT_ID)
    }


def _yaml_entry_data(object_id: str, cfg: ConfigType) -> dict[str, Any]:
    """Return normalized config-entry data for one YAML room."""
    sensors = cfg.get(CONF_SENSORS) or list(SENSORS.keys())
    return {
        CONF_OBJECT_ID: object_id,
        CONF_NAME: cfg.get(CONF_NAME, _deslugify(object_id)),
        CONF_SOURCES: cfg[CONF_SOURCES],
        CONF_SENSORS: sensors,
    }


async def _async_import_yaml_config(
    hass: HomeAssistant, yaml_config: dict[str, ConfigType]
) -> None:
    """Import or sync YAML rooms after startup without blocking HA boot."""
    current_entries = {
        entry.data.get(CONF_OBJECT_ID): entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_OBJECT_ID)
    }

    for object_id, cfg in yaml_config.items():
        try:
            data = _yaml_entry_data(object_id, cfg)
            entry = current_entries.get(object_id)
            if entry is not None:
                if (
                    entry.data == data
                    and entry.title == data[CONF_NAME]
                    and not entry.options
                ):
                    continue

                _LOGGER.info(
                    "Sync IAQCA YAML room %s to existing config entry", object_id
                )
                hass.config_entries.async_update_entry(
                    entry, title=data[CONF_NAME], data=data, options={}
                )
                if entry.disabled_by is None:
                    await hass.config_entries.async_reload(entry.entry_id)
                continue

            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=data,
            )
        except Exception:  # pragma: no cover - defensive startup guard
            _LOGGER.exception("Failed to import IAQCA YAML room %s", object_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import YAML rooms into config entries without creating duplicate YAML entities."""
    yaml_config: dict[str, ConfigType] = {}
    if LEGACY_DOMAIN in config:
        _LOGGER.warning(
            "The iaquk YAML key is deprecated; use iaqca instead. Importing legacy IAQCA config."
        )
        yaml_config.update(config[LEGACY_DOMAIN])
    if DOMAIN in config:
        yaml_config.update(config[DOMAIN])
    if not yaml_config:
        return True

    _LOGGER.info(STARTUP_MESSAGE)
    _ensure_domain_data(hass)

    @callback
    def _schedule_yaml_import(event: Event | None = None) -> None:
        _LOGGER.info(
            "Schedule IAQCA YAML config import/sync for %d rooms", len(yaml_config)
        )
        hass.async_create_background_task(
            _async_import_yaml_config(hass, dict(yaml_config)),
            "IAQCA YAML config import/sync",
        )

    if hass.is_running:
        _schedule_yaml_import()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _schedule_yaml_import)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IAQCA from a config entry."""
    data = _ensure_domain_data(hass)
    object_id = entry.data[CONF_OBJECT_ID]
    name = entry.data.get(CONF_NAME, _deslugify(object_id))
    sources = entry.data[CONF_SOURCES]
    sensors = entry.options.get(CONF_SENSORS, entry.data.get(CONF_SENSORS))

    if not sensors:
        sensors = list(SENSORS.keys())

    controller = IaqcaController(hass, object_id, name, sources)
    data[DATA_CONTROLLERS][object_id] = controller
    data[DATA_ENTRY_CONTROLLERS][entry.entry_id] = {
        CONF_OBJECT_ID: object_id,
        "controller": controller,
        CONF_SENSORS: sensors,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, [SENSOR])
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an IAQCA config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, [SENSOR])
    if unloaded:
        data = _ensure_domain_data(hass)
        entry_data = data[DATA_ENTRY_CONTROLLERS].pop(entry.entry_id, None)
        if entry_data is not None:
            object_id = entry_data[CONF_OBJECT_ID]
            controller = entry_data["controller"]
            controller.async_shutdown()
            if data[DATA_CONTROLLERS].get(object_id) is controller:
                data[DATA_CONTROLLERS].pop(object_id)

    return unloaded


class IaqcaController:
    """IAQCA controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        name: str,
        sources: dict[str, str | list[str]],
    ) -> None:
        """Initialize controller."""
        self.hass = hass
        self._entity_id = entity_id
        self._name = name
        self._sources = sources

        self._iaq_index = None
        self._iaq_sources = 0
        self._added = False
        self._indexes = {}
        self._source_values = {}
        self._source_status = {}
        self._source_problems = []
        self._listeners: list[Callable[[], None]] = []
        self._remove_state_listener: Callable[[], None] | None = None
        self._remove_start_listener: Callable[[], None] | None = None

    def async_added_to_hass(self) -> None:
        """Register callbacks."""
        if self._added:
            return

        # pylint: disable=unused-argument
        # pragma: no cover
        @callback
        def sensor_state_listener(event: Event) -> None:  # noqa: ARG001
            """Handle device state changes."""
            self.update()

        # pylint: disable=unused-argument
        @callback
        def setup_tracking(event: Event | None = None) -> None:  # noqa: ARG001
            """Track configured source entities and calculate the first value."""
            entity_ids = []
            for src in self._sources.values():
                if isinstance(src, list):
                    entity_ids.extend(src)
                else:
                    entity_ids.append(src)

            _LOGGER.debug(
                "[%s] Setup states tracking for %s",
                self._entity_id,
                ", ".join(entity_ids),
            )

            self._remove_start_listener = None
            self._remove_state_listener = async_track_state_change_event(
                self.hass, entity_ids, sensor_state_listener
            )
            self.update()  # Force first update

        self._added = True
        if self.hass.is_running:
            setup_tracking()
        else:
            self._remove_start_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, setup_tracking
            )

    def async_shutdown(self) -> None:
        """Release registered callbacks."""
        if self._remove_start_listener is not None:
            self._remove_start_listener()
            self._remove_start_listener = None
        if self._remove_state_listener is not None:
            self._remove_state_listener()
            self._remove_state_listener = None
        self._listeners.clear()
        self._added = False

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for calculated IAQ changes."""
        self._listeners.append(listener)

        def remove_listener() -> None:
            """Remove a previously registered listener."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    def _notify_listeners(self) -> None:
        """Notify entities that the calculated value changed."""
        for listener in list(self._listeners):
            listener()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._entity_id

    @property
    def name(self) -> str:
        """Get controller name."""
        return self._name

    @property
    def iaq_index(self) -> int | None:
        """Get IAQ index."""
        return self._iaq_index

    # pylint: disable=R1705
    @property
    def iaq_level(self) -> str | None:
        """Get IAQ level."""
        # Transform IAQ index to human-readable IAQCA level text.
        if self._iaq_index is None:
            return None
        if self._iaq_index <= 25:  # noqa: PLR2004
            return LEVEL_INADEQUATE
        if self._iaq_index <= 38:  # noqa: PLR2004
            return LEVEL_POOR
        if self._iaq_index <= 51:  # noqa: PLR2004
            return LEVEL_FAIR
        if self._iaq_index <= 60:  # noqa: PLR2004
            return LEVEL_GOOD
        return LEVEL_EXCELLENT

    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        state_attr = {
            ATTR_ADVISORY_PROFILE: ADVISORY_PROFILE,
            ATTR_SCORING_PROFILE: SCORING_PROFILE,
            ATTR_SOURCES_SET: len(self._sources),
            ATTR_SOURCES_USED: self._iaq_sources,
        }

        available_sources = sorted(self._indexes)
        unavailable_sources = sorted(set(self._sources) - set(self._indexes))
        if available_sources:
            state_attr[ATTR_AVAILABLE_SOURCES] = available_sources
        if unavailable_sources:
            state_attr[ATTR_UNAVAILABLE_SOURCES] = unavailable_sources

        for src, idx in self._indexes.items():
            state_attr[ATTR_SOURCE_INDEX_TPL.format(src)] = idx
        if self._source_values:
            state_attr[ATTR_SOURCE_VALUES] = self._source_values
            state_attr[ATTR_SOURCE_SUMMARY] = self._source_summary
        if self._source_status:
            state_attr[ATTR_SOURCE_STATUS] = self._source_status
            state_attr[ATTR_ADVISORY_STATUS] = self._advisory_status
            active_issues = self._active_issues
            if active_issues:
                state_attr[ATTR_ACTIVE_ISSUES] = active_issues
        if self._source_problems:
            state_attr[ATTR_SOURCE_PROBLEMS] = self._source_problems
        if self._indexes:
            worst_index = min(self._indexes.values())
            state_attr[ATTR_WORST_SOURCE_INDEX] = worst_index
            state_attr[ATTR_WORST_SOURCES] = [
                source
                for source, index in self._indexes.items()
                if index == worst_index
            ]
        state_attr[ATTR_CALCULATION_SUMMARY] = self._calculation_summary

        return state_attr

    @property
    def _source_summary(self) -> list[str]:
        """Return human-readable source rows for the more-info attributes view."""
        rows = []
        for source_type in sorted(self._source_values):
            index = self._indexes.get(source_type)
            status = ", ".join(self._source_status.get(source_type, [])) or "unknown"
            for reading in self._source_values[source_type]:
                unit = reading.get("unit") or ""
                rows.append(
                    f"{source_type}: {reading['value']} {unit} "
                    f"from {reading['entity_id']} "
                    f"(index {index if index is not None else 'n/a'}, {status})"
                )
        return rows

    @property
    def _calculation_summary(self) -> dict[str, Any]:
        """Return a compact summary of the current calculation."""
        sources_set = len(self._sources)
        available_sources = sorted(self._indexes)
        unavailable_sources = sorted(set(self._sources) - set(self._indexes))
        worst_index = min(self._indexes.values()) if self._indexes else None
        worst_sources = (
            [source for source, index in self._indexes.items() if index == worst_index]
            if worst_index is not None
            else []
        )

        return {
            "index": self._iaq_index,
            "level": self.iaq_level,
            "advisory_status": self._advisory_status if self._source_status else None,
            "sources_set": sources_set,
            "sources_used": self._iaq_sources,
            "source_coverage": round(self._iaq_sources / sources_set, 3)
            if sources_set
            else 0,
            "available_sources": available_sources,
            "unavailable_sources": unavailable_sources,
            "worst_source_index": worst_index,
            "worst_sources": worst_sources,
        }

    @property
    def _advisory_status(self) -> str:
        """Return the highest-severity advisory status."""
        status = "good"
        severity = STATUS_SEVERITY[status]
        for statuses in self._source_status.values():
            for candidate in statuses:
                candidate_severity = STATUS_SEVERITY.get(candidate, 0)
                if candidate_severity > severity:
                    status = candidate
                    severity = candidate_severity
        return status

    @property
    def _active_issues(self) -> list[str]:
        """Return current source types that are outside a good/acceptable range."""
        issues = []
        for source_type, statuses in self._source_status.items():
            for status in statuses:
                if STATUS_SEVERITY.get(status, 0) >= STATUS_SEVERITY["out_of_range"]:
                    issues.append(f"{source_type}:{status}")
        return sorted(
            set(issues),
            key=lambda item: (
                -STATUS_SEVERITY.get(item.split(":", 1)[1], 0),
                item,
            ),
        )

    def update(self) -> None:
        """Update index state."""
        _LOGGER.debug("[%s] State update", self._entity_id)

        iaq = 0
        sources = 0
        indexes = {}
        old_source_values = self._source_values
        old_source_status = self._source_status
        old_source_problems = self._source_problems
        self._source_values = {}
        self._source_status = {}
        self._source_problems = []
        for src in self._sources:
            try:
                # pylint: disable=unnecessary-dunder-call
                idx = self.__getattribute__(f"_{src}_index")
                _LOGGER.debug("[%s] %s_index=%s", self._entity_id, src, idx)
                if idx is not None:
                    iaq += idx
                    sources += 1
                    indexes[src] = idx
            except Exception:
                _LOGGER.exception("Exception occurred")

        if sources:
            iaq_index = int((65 * iaq) / (5 * sources))
            changed = (
                iaq_index != self._iaq_index
                or sources != self._iaq_sources
                or indexes != self._indexes
                or self._source_values != old_source_values
                or self._source_status != old_source_status
                or self._source_problems != old_source_problems
            )
            self._indexes = indexes
            self._iaq_index = iaq_index
            self._iaq_sources = int(sources)
            _LOGGER.debug(
                "[%s] Update IAQ index to %d (%d sources used)",
                self._entity_id,
                self._iaq_index,
                self._iaq_sources,
            )
            if changed:
                self._notify_listeners()
            return

        changed = (
            self._iaq_index is not None
            or self._iaq_sources
            or self._indexes
            or self._source_values != old_source_values
            or self._source_status != old_source_status
            or self._source_problems != old_source_problems
        )
        self._indexes = {}
        self._source_values = {}
        self._source_status = {}
        self._source_problems = []
        self._iaq_index = None
        self._iaq_sources = 0
        if changed:
            _LOGGER.debug("[%s] No IAQ sources currently available", self._entity_id)
            self._notify_listeners()

    @staticmethod
    def _has_state(state: str | None) -> bool:
        """Return True if state has any value."""
        return state is not None and state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]

    def _record_source_value(
        self,
        source_type: str,
        entity_id: str,
        value: float,
        unit: str | None,
    ) -> None:
        """Record a converted source value used for the current calculation."""
        if not source_type:
            return

        self._source_values.setdefault(source_type, []).append(
            {
                "entity_id": entity_id,
                "value": round(value, 4),
                "unit": unit,
            }
        )

    def _record_source_problem(
        self,
        source_type: str,
        entity_id: str,
        reason: str,
        detail: str | None = None,
    ) -> None:
        """Record why a configured source was not used."""
        problem = {
            "source": source_type,
            "entity_id": entity_id,
            "reason": reason,
        }
        if detail is not None:
            problem["detail"] = detail
        self._source_problems.append(problem)

    def _record_source_status(self, source_type: str, value: float) -> None:
        """Record advisory status for known indoor air source types."""
        status = None

        if source_type == CONF_CO2:
            if value <= 1000:  # ppm
                status = "good"
            elif value <= 1800:  # ppm
                status = "elevated"
            else:
                status = "high"
        elif source_type == CONF_CO:
            if value <= 11.5:  # mg/m3, Health Canada 24h residential limit
                status = "good"
            elif value <= 28.6:  # mg/m3, Health Canada 1h residential limit
                status = "elevated"
            else:
                status = "high"
        elif source_type == CONF_PM:
            if value <= 15:  # ug/m3, WELL-style conservative target
                status = "good"
            elif value <= 35:  # ug/m3, common continuous-monitoring action level
                status = "elevated"
            else:
                status = "high"
        elif source_type == CONF_TVOC:
            if value <= 0.5:  # mg/m3, equivalent to 500 ug/m3
                status = "good"
            elif value <= 1.0:  # mg/m3
                status = "elevated"
            else:
                status = "high"
        elif source_type == CONF_HCHO:
            if value <= 50:  # ug/m3, Health Canada 8h residential limit
                status = "good"
            elif value <= 123:  # ug/m3, Health Canada 1h residential limit
                status = "elevated"
            else:
                status = "high"
        elif source_type == CONF_NO2:
            if value <= 0.02:  # mg/m3, 20 ug/m3 Health Canada 24h limit
                status = "good"
            elif value <= 0.17:  # mg/m3, 170 ug/m3 Health Canada 1h limit
                status = "elevated"
            else:
                status = "high"
        elif source_type == CONF_RADON:
            status = "good" if value < 200 else "high"  # Bq/m3
        elif source_type == CONF_HUMIDITY:
            if 40 <= value <= 60:
                status = "good"
            elif 30 <= value <= 70:
                status = "acceptable"
            else:
                status = "out_of_range"
        elif source_type == CONF_TEMPERATURE:
            if 18 <= value <= 23:
                status = "good"
            elif 16 <= value <= 25:
                status = "acceptable"
            else:
                status = "out_of_range"
        elif source_type == CONF_VOC_INDEX:
            if value <= 50:
                status = "good"
            elif value <= 115:
                status = "acceptable"
            elif value <= 180:
                status = "elevated"
            else:
                status = "high"

        if status is not None:
            statuses = self._source_status.setdefault(source_type, [])
            if status not in statuses:
                statuses.append(status)
                statuses.sort(key=lambda item: -STATUS_SEVERITY.get(item, 0))

    def _get_number_state(
        self,
        entity_id: str,
        entity_unit: str | None = None,
        source_type: str = "",
        mweight: float | None = None,
    ) -> float | None:
        """Convert value to number."""
        target_unit = None
        if entity_unit is not None and not isinstance(entity_unit, dict):
            entity_unit = {entity_unit: 1}

        entity = self.hass.states.get(entity_id)
        if entity is None:
            _LOGGER.warning("Entity %s not found", entity_id)
            self._record_source_problem(source_type, entity_id, "not_found")
            return None
        if not isinstance(entity, State):  # pragma: no cover
            _LOGGER.warning("State of entity %s be instance of class State", entity_id)
            self._record_source_problem(source_type, entity_id, "invalid_state")
            return None

        value = entity.state
        unit = entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        _LOGGER.debug(
            "[%s] %s=%s %s",
            self._entity_id,
            entity_id,
            value,
            (unit if unit and self._has_state(value) else ""),
        )
        if not self._has_state(value):
            _LOGGER.debug("State of entity %s is unknown", entity_id)
            self._record_source_problem(source_type, entity_id, "unavailable", value)
            return None

        if entity_unit is not None:
            target_unit = next(iter(entity_unit))
            if unit not in entity_unit:
                # pylint: disable=R1705
                if mweight is None:
                    _LOGGER.debug(
                        'Entity %s has inappropriate "%s" '
                        "units for %s source. Ignored.",
                        entity_id,
                        unit,
                        source_type,
                    )
                    self._record_source_problem(
                        source_type, entity_id, "invalid_unit", str(unit)
                    )
                    return None
                entity_unit = entity_unit.copy()
                if "ppb" in (unit, target_unit):
                    mweight /= 1000
                if "µg/m³" in (unit, target_unit):
                    mweight *= 1000
                if unit in {"ppm", "ppb"}:
                    entity_unit[unit] = mweight / 24.45
                else:
                    entity_unit[unit] = 24.45 / mweight

        try:
            value = float(value)
        except (TypeError, ValueError):
            self._record_source_problem(source_type, entity_id, "not_numeric", value)
            return None

        if entity_unit is not None and unit != target_unit:
            if unit not in entity_unit:
                self._record_source_problem(
                    source_type, entity_id, "invalid_unit", str(unit)
                )
                return None
            value *= entity_unit[unit]
            unit = target_unit
            _LOGGER.debug(
                "[%s] %s=%s %s (converted)",
                self._entity_id,
                entity_id,
                value,
                target_unit,
            )
        self._record_source_value(source_type, entity_id, value, unit)
        if source_type not in (CONF_PM, CONF_TEMPERATURE):
            self._record_source_status(source_type, value)
        return value

    @property
    def _temperature_index(self) -> int | None:
        """Transform indoor temperature values to IAQ points."""
        entity_id = self._sources.get(CONF_TEMPERATURE)
        if entity_id is None:
            return None

        value = self._get_number_state(entity_id, source_type=CONF_TEMPERATURE)
        if value is None:
            return None

        entity = self.hass.states.get(entity_id)
        entity_unit = entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if entity_unit not in (UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT):
            raise ValueError(
                UNIT_NOT_RECOGNIZED_TEMPLATE.format(entity_unit, TEMPERATURE)
            )

        if entity_unit != UnitOfTemperature.CELSIUS:
            value = TemperatureConverter.convert(
                value, entity_unit, UnitOfTemperature.CELSIUS
            )
        self._record_source_status(CONF_TEMPERATURE, value)

        index = 1
        if 18 <= value <= 21:  # °C     # noqa: PLR2004
            index = 5
        elif 16 < value < 23:  # °C     # noqa: PLR2004
            index = 4
        elif 15 < value < 24:  # °C     # noqa: PLR2004
            index = 3
        elif 14 < value < 25:  # °C     # noqa: PLR2004
            index = 2
        return index

    @staticmethod
    def _health_canada_guideline_index(
        value: float, long_term_limit: float, short_term_limit: float
    ) -> int:
        """Return five IAQ points from Health Canada guideline limits.

        The long-term guideline defines the transition from good to elevated.
        The midpoint between long- and short-term limits provides a stable
        intermediate band without presenting this derived score as an official
        Health Canada index.
        """
        if value <= long_term_limit * 0.5:
            return 5
        if value <= long_term_limit:
            return 4
        if value <= (long_term_limit + short_term_limit) / 2:
            return 3
        if value <= short_term_limit:
            return 2
        return 1

    @property
    def _humidity_index(self) -> int | None:
        """Transform indoor humidity values to IAQ points."""
        entity_id = self._sources.get(CONF_HUMIDITY)
        if entity_id is None:
            return None

        value = self._get_number_state(entity_id, PERCENTAGE, CONF_HUMIDITY)
        if value is None:
            return None

        index = 1
        if 40 <= value <= 60:  # %      # noqa: PLR2004
            index = 5
        elif 30 <= value <= 70:  # %    # noqa: PLR2004
            index = 4
        elif 20 <= value <= 80:  # %    # noqa: PLR2004
            index = 3
        elif 10 <= value <= 90:  # %    # noqa: PLR2004
            index = 2
        return index

    @property
    def _co2_index(self) -> int | None:
        """Transform indoor eCO2 values to Health Canada IAQ points."""
        entity_id = self._sources.get(CONF_CO2)
        if entity_id is None:
            return None

        value = self._get_number_state(
            entity_id, UNIT_PPM, CONF_CO2, mweight=MWEIGTH_CO2
        )
        if value is None:
            return None

        # Health Canada residential guideline: 1000 ppm (24-hour average).
        if value <= 500:
            return 5
        if value <= 750:
            return 4
        if value <= 1000:
            return 3
        if value <= 1800:
            return 2
        return 1

    @property
    def _tvoc_index(self) -> int | None:
        """Transform indoor tVOC values to IAQ points."""
        entity_id = self._sources.get(CONF_TVOC)
        if entity_id is None:
            return None

        value = self._get_number_state(
            entity_id, UNIT_MGM3, CONF_TVOC, mweight=MWEIGTH_TVOC
        )
        if value is None:
            return None

        index = 1
        if value < 0.1:  # mg/m³        # noqa: PLR2004
            index = 5
        elif value <= 0.3:  # mg/m³     # noqa: PLR2004
            index = 4
        elif value <= 0.5:  # mg/m³     # noqa: PLR2004
            index = 3
        elif value <= 1.0:  # mg/m³
            index = 2
        return index

    @property
    def _voc_index_index(self) -> int | None:
        """
        Transform indoor VOC index (0-500) values to IAQ points.

        Especially for SGP40 and SGP41 gas sensors:
            0-50    — Good
            51-100  — Moderate
            101-150 — Unhealthy for sensitive peoples
            151-200 — Unhealthy
            201-300 — Very unhealthy
            301-500 — Hazardous
        """
        entity_id = self._sources.get(CONF_VOC_INDEX)
        if entity_id is None:
            return None

        value = self._get_number_state(entity_id, None, CONF_VOC_INDEX)
        if value is None:
            return None

        index = 1
        if value <= 50:  # noqa: PLR2004
            index = 5
        elif value <= 115:  # noqa: PLR2004
            index = 4
        elif value <= 180:  # noqa: PLR2004
            index = 3
        elif value <= 260:  # noqa: PLR2004
            index = 2
        return index

    @property
    def _pm_index(self) -> int | None:
        """Transform indoor particulate matters values to IAQ points."""
        entity_ids = self._sources.get(CONF_PM)
        if entity_ids is None or entity_ids == []:
            return None

        values = []
        for eid in entity_ids:
            val = self._get_number_state(eid, UNIT_UGM3, CONF_PM)
            if val is None:
                continue
            values.append(val)

        if not values:
            return None

        value = sum(values)
        self._record_source_status(CONF_PM, value)
        index = 1
        if value <= 23:  # µg/m3    # noqa: PLR2004
            index = 5
        elif value <= 41:  # µg/m3  # noqa: PLR2004
            index = 4
        elif value <= 53:  # µg/m3  # noqa: PLR2004
            index = 3
        elif value <= 64:  # µg/m3  # noqa: PLR2004
            index = 2
        return index

    @property
    def _no2_index(self) -> int | None:
        """Transform indoor NO2 values to Health Canada IAQ points."""
        entity_id = self._sources.get(CONF_NO2)
        if entity_id is None:
            return None

        value = self._get_number_state(
            entity_id, UNIT_MGM3, CONF_NO2, mweight=MWEIGTH_NO2
        )
        if value is None:
            return None

        # Health Canada: 0.02 mg/m3 (24 h), 0.17 mg/m3 (1 h).
        return self._health_canada_guideline_index(value, 0.02, 0.17)

    @property
    def _co_index(self) -> int | None:
        """Transform indoor CO values to Health Canada IAQ points."""
        entity_ids = self._sources.get(CONF_CO)
        if entity_ids is None or entity_ids == []:
            return None

        if not isinstance(entity_ids, list):
            entity_ids = [entity_ids]

        values = []
        for entity_id in entity_ids:
            value = self._get_number_state(
                entity_id, UNIT_MGM3, CONF_CO, mweight=MWEIGTH_CO
            )
            if value is not None:
                values.append(value)

        if not values:
            return None

        # Health Canada: 11.5 mg/m3 (24 h), 28.6 mg/m3 (1 h).
        return self._health_canada_guideline_index(max(values), 11.5, 28.6)

    @property
    def _hcho_index(self) -> int | None:
        """Transform indoor formaldehyde values to Health Canada IAQ points."""
        entity_id = self._sources.get(CONF_HCHO)
        if entity_id is None:
            return None

        value = self._get_number_state(
            entity_id, UNIT_UGM3, CONF_HCHO, mweight=MWEIGTH_HCHO
        )
        if value is None:
            return None

        # Health Canada: 50 ug/m3 (8 h), 123 ug/m3 (1 h).
        return self._health_canada_guideline_index(value, 50, 123)

    @property
    def _radon_index(self) -> int | None:
        """Transform indoor radon values to Health Canada IAQ points."""
        entity_id = self._sources.get(CONF_RADON)
        if entity_id is None:
            return None

        value = self._get_number_state(entity_id, "Bq/m3", CONF_RADON)
        if value is None:
            return None

        # Health Canada recommends remediation above 200 Bq/m3.
        if value <= 50:
            return 5
        if value <= 100:
            return 4
        if value <= 200:
            return 3
        if value <= 400:
            return 2
        return 1
