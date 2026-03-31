"""Binary sensor platform for IronLogic."""

import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    host = data["host"]

    async def async_update_data():
        try:
            return await api.check_availability()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"IronLogic {host}",
        update_method=async_update_data,
        update_interval=timedelta(
            seconds=data.get("poll_interval", DEFAULT_POLL_INTERVAL)
        ),
    )

    await coordinator.async_config_entry_first_refresh()
    data["availability_coordinator"] = coordinator

    sensors = [IronLogicAvailabilitySensor(coordinator, entry, data)]

    if data.get("use_door_sensor", False):
        door_sensor = IronLogicDoorSensor(entry, data)
        sensors.append(door_sensor)
        data["door_sensor_entity"] = door_sensor
        _LOGGER.debug("Door sensor created and stored")

    async_add_entities(sensors)


class IronLogicAvailabilitySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "controller_availability"

    def __init__(self, coordinator, entry, data):
        super().__init__(coordinator)
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_availability"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._attr_is_on = coordinator.data if coordinator.data is not None else False

    @property
    def is_on(self) -> bool:
        return self.coordinator.data if self.coordinator.data is not None else False

    @property
    def available(self) -> bool:
        return True

    async def async_added_to_hass(self):
        """Subscribe to coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        is_available = (
            self.coordinator.data if self.coordinator.data is not None else False
        )
        self.hass.bus.async_fire(
            f"{DOMAIN}_availability_updated", {"available": is_available}
        )


class IronLogicDoorSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_translation_key = "door"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_door"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._attr_is_on = False
        self._unsub = None
        self._availability_sub = None
        self._controller_available = True

    @property
    def icon(self) -> str:
        return "mdi:door-open" if self._attr_is_on else "mdi:door-closed"

    @property
    def available(self) -> bool:
        """Return if sensor is available (controller must be reachable)."""
        return self._controller_available

    async def async_added_to_hass(self):
        self._unsub = self.hass.bus.async_listen(
            f"{DOMAIN}_update_sensor", self._handle_update
        )
        self._availability_sub = self.hass.bus.async_listen(
            f"{DOMAIN}_availability_updated", self._handle_availability_update
        )

    async def async_will_remove_from_hass(self):
        if self._unsub:
            self._unsub()
        if self._availability_sub:
            self._availability_sub()

    @callback
    def _handle_availability_update(self, event):
        available = event.data.get("available", False)
        if self._controller_available != available:
            self._controller_available = available
            self.async_write_ha_state()
            _LOGGER.debug(
                "Door sensor availability updated to: %s",
                "available" if available else "unavailable",
            )

    @callback
    def _handle_update(self, event):
        event_code = event.data.get("event_code")
        if event_code in (0x20, 0x21, 0x0C, 0x0D):
            self.update_state(True)
        elif event_code in (0x22, 0x23):
            self.update_state(False)

    def update_state(self, is_open: bool) -> None:
        if self._attr_is_on != is_open:
            self._attr_is_on = is_open
            self.async_write_ha_state()
            _LOGGER.debug("Door state updated: %s", "open" if is_open else "closed")