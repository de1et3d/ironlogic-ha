"""Number platform for IronLogic controls."""

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_POLL_INTERVAL
from . import async_update_entry_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IronLogic number controls."""
    data = hass.data[DOMAIN][entry.entry_id]

    numbers = [
        IronLogicPollIntervalNumber(entry, data),
    ]
    async_add_entities(numbers)


class IronLogicPollIntervalNumber(NumberEntity):
    """Number to set poll interval."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 10
    _attr_native_max_value = 3600
    _attr_native_step = 5
    _attr_unit_of_measurement = "seconds"
    _attr_translation_key = "poll_interval"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the number."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_poll_interval"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._attr_native_value = data.get("poll_interval", DEFAULT_POLL_INTERVAL)

    async def async_set_native_value(self, value: float) -> None:
        """Set new poll interval."""
        interval = int(value)
        await async_update_entry_data(
            self.hass, self._entry.entry_id, poll_interval=interval
        )
        self._data["poll_interval"] = interval
        self._attr_native_value = interval
        self.async_write_ha_state()
        coordinator = self._data.get("availability_coordinator")
        if coordinator:
            coordinator.update_interval = interval
        _LOGGER.debug("Poll interval set to %d seconds", interval)