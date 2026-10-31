"""Diagnostics support for Canadian Air Quality Index."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DATA_ENTRY_CONTROLLERS
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = (
        hass.data.get(DOMAIN, {}).get(DATA_ENTRY_CONTROLLERS, {}).get(entry.entry_id)
    )
    controller = entry_data["controller"] if entry_data else None

    diagnostics: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "runtime": {
            "loaded": controller is not None,
        },
    }

    if controller is not None:
        diagnostics["runtime"].update(
            {
                "iaq_index": controller.iaq_index,
                "iaq_level": controller.iaq_level,
                "attributes": controller.state_attributes,
            }
        )

    return diagnostics
