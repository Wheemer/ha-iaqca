"""Identify documented gas-index scales without inferring them from values."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

AUTO = "auto"
BOSCH_BSEC = "bosch_bsec"
SENSIRION_VOC = "sensirion_voc"
INDEX_PROFILES = (AUTO, BOSCH_BSEC, SENSIRION_VOC)


def detect_index_profile(hass: HomeAssistant, entity_id: str) -> str | None:
    """Use identity, device metadata and BSEC sibling outputs, never a value."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    unit = state.attributes.get("unit_of_measurement")
    if unit not in (None, "", "IAQ", "VOC Index", "VOC index"):
        return None
    identity = f"{entity_id} {state.name}".lower().replace("_", " ")
    if (
        "accuracy" in identity
        or "calibration" in identity
        or state.attributes.get("scoring_profile")
    ):
        return None
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    device = (
        dr.async_get(hass).async_get(entry.device_id)
        if entry is not None and entry.device_id is not None
        else None
    )
    metadata = (
        f"{device.manufacturer or ''} {device.model or ''}".lower()
        if device is not None
        else ""
    )
    siblings = []
    if device is not None:
        siblings = [
            f"{item.entity_id} {item.original_name or ''}".lower().replace("_", " ")
            for item in er.async_entries_for_device(registry, device.id)
        ]
    bsec_siblings = any("breath voc equivalent" in name for name in siblings) and any(
        "co2 equivalent" in name for name in siblings
    )
    bosch = ("iaq" in identity or unit == "IAQ") and (
        "bsec" in identity
        or "bosch" in identity
        or "bme68" in metadata
        or bsec_siblings
    )
    sensirion = ("voc index" in identity or unit in ("VOC Index", "VOC index")) and (
        "sensirion" in identity
        or "sensirion" in metadata
        or any(model in metadata for model in ("sgp40", "sgp41", "sen5"))
    )
    if bosch == sensirion:
        return None
    return BOSCH_BSEC if bosch else SENSIRION_VOC


def index_points(value: float, profile: str) -> int:
    """Convert a known scale into IAQCA's five operational points."""
    boundaries = {
        BOSCH_BSEC: (50, 100, 150, 200),
        SENSIRION_VOC: (50, 115, 180, 260),
    }[profile]
    return 5 - sum(value > boundary for boundary in boundaries)


def equivalent_context(
    hass: HomeAssistant, entity_id: str
) -> tuple[str, str | None] | None:
    """Identify a labelled estimate and its same-device native index, if known."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)
    identity = f"{entity_id} {state.name if state else ''} {entry.original_name if entry else ''}".lower()
    if "equivalent" not in identity:
        return None
    if entry is None or entry.device_id is None:
        return (entity_id, None)
    native = sorted(
        item.entity_id
        for item in er.async_entries_for_device(registry, entry.device_id)
        if detect_index_profile(hass, item.entity_id) == BOSCH_BSEC
    )
    # Multiple different index outputs are ambiguous; retain proxy scoring.
    return (entry.device_id, native[0] if len(native) == 1 else None)
