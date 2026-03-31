"""Switch platform for IronLogic controls."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from . import async_update_entry_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IronLogic switch controls."""
    data = hass.data[DOMAIN][entry.entry_id]

    switches = [
        IronLogicDoorSensorSwitch(entry, data),
    ]
    async_add_entities(switches)


class IronLogicDoorSensorSwitch(SwitchEntity):
    """Switch to enable/disable door sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "door_sensor"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the switch."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_door_sensor_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._attr_is_on = data.get("use_door_sensor", False)

    async def async_turn_on(self, **kwargs):
        """Enable door sensor."""
        await async_update_entry_data(
            self.hass, self._entry.entry_id, use_door_sensor=True
        )
        self._data["use_door_sensor"] = True
        self._attr_is_on = True
        self.async_write_ha_state()
        await self.hass.config_entries.async_reload(self._entry.entry_id)

    async def async_turn_off(self, **kwargs):
        """Disable door sensor."""
        await async_update_entry_data(
            self.hass, self._entry.entry_id, use_door_sensor=False
        )
        self._data["use_door_sensor"] = False
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.hass.config_entries.async_reload(self._entry.entry_id)