"""Lock platform for IronLogic."""

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_COMMAND_COOLDOWN, DEFAULT_OPEN_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IronLogic lock platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]

    lock = IronLogicDoorLock(hass, entry, data, api)
    async_add_entities([lock])

    data["locks"][entry.entry_id] = lock

    async def add_key(call):
        await lock.async_add_key(
            call.data.get("key_number"),
            call.data.get("name", ""),
            call.data.get("key_type", "normal"),
        )

    async def remove_key(call):
        await lock.async_remove_key(call.data.get("key_number"))

    async def clear_all_keys(call):
        await lock.async_clear_all_keys()

    hass.services.async_register(DOMAIN, "add_key", add_key)
    hass.services.async_register(DOMAIN, "remove_key", remove_key)
    hass.services.async_register(DOMAIN, "clear_all_keys", clear_all_keys)

class IronLogicDoorLock(LockEntity):
    """Representation of IronLogic door lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "door_lock"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, data: dict[str, Any], api
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._data = data
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_lock"
        self._attr_is_locked = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._last_command_time = 0
        self._pending_commands = []
        self._reset_lock_task = None
        self._availability_sub = None
        self._controller_available = True

    @property
    def icon(self) -> str:
        return "mdi:lock" if self._attr_is_locked else "mdi:lock-open-variant"

    @property
    def available(self) -> bool:
        """Return if lock is available (controller must be reachable)."""
        return self._controller_available

    async def async_added_to_hass(self):
        """Subscribe to availability updates."""
        await super().async_added_to_hass()
        self._availability_sub = self.hass.bus.async_listen(
            f"{DOMAIN}_availability_updated", self._handle_availability_update
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from availability updates."""
        if self._availability_sub:
            self._availability_sub()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_availability_update(self, event):
        """Handle availability change."""
        available = event.data.get("available", False)
        if self._controller_available != available:
            self._controller_available = available
            self.async_write_ha_state()
            _LOGGER.debug(
                "Lock availability updated to: %s",
                "available" if available else "unavailable",
            )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Open the door."""
        if not self._controller_available:
            _LOGGER.warning("Cannot unlock - controller is unavailable")
            return

        now = time.time()
        if now - self._last_command_time < DEFAULT_COMMAND_COOLDOWN:
            _LOGGER.warning("Command ignored (cooldown)")
            return

        self._last_command_time = now
        _LOGGER.debug("Unlocking door for %s", self._data["host"])

        success = await self._api.open_door()

        if success:
            _LOGGER.debug("Door opened via HTTP API")
            self._attr_is_locked = False
            self.async_write_ha_state()
        else:
            _LOGGER.debug("HTTP API failed, queueing command")
            self._pending_commands.append({"operation": "open_door", "direction": 0})
            self._attr_is_locked = False
            self.async_write_ha_state()

        if self._reset_lock_task and not self._reset_lock_task.done():
            self._reset_lock_task.cancel()

        async def reset_lock() -> None:
            try:
                await asyncio.sleep(DEFAULT_OPEN_TIME)
                if not self._attr_is_locked:
                    self._attr_is_locked = True
                    self.async_write_ha_state()
                    _LOGGER.debug(
                        "Lock auto-closed after %d seconds", DEFAULT_OPEN_TIME
                    )
            except asyncio.CancelledError:
                _LOGGER.debug("Auto-lock task cancelled")

        self._reset_lock_task = asyncio.create_task(reset_lock())

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock is not supported (momentary lock)."""
        pass

    def get_pending_commands(self) -> list[dict[str, Any]]:
        commands = self._pending_commands.copy()
        self._pending_commands.clear()
        return commands

    async def async_add_key(
        self, key_number: str, name: str = "", key_type: str = "normal"
    ):
        flags = 8 if key_type == "blocking" else 0

        if "keys" not in self._data:
            self._data["keys"] = []

        key_data = {
            "key_number": key_number,
            "name": name,
            "type": key_type,
            "flags": flags,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._data["keys"].append(key_data)
        if self._data.get("keys_store"):
            await self._data["keys_store"].async_save({"keys": self._data["keys"]})

        self._pending_commands.append(
            {
                "operation": "add_keys",
                "keys": [{"key": key_number, "flags": flags, "tz": 255}],
            }
        )
        _LOGGER.info("Key %s (%s) added to queue", key_number, name)

    async def async_remove_key(self, key_number: str):
        if "keys" in self._data:
            self._data["keys"] = [
                k for k in self._data["keys"] if k.get("key_number") != key_number
            ]
            if self._data.get("keys_store"):
                await self._data["keys_store"].async_save({"keys": self._data["keys"]})

        self._pending_commands.append(
            {"operation": "del_keys", "keys": [{"key": key_number}]}
        )
        _LOGGER.info("Key %s removal queued", key_number)

    async def async_clear_all_keys(self):
        if "keys" in self._data:
            self._data["keys"] = []
            if self._data.get("keys_store"):
                await self._data["keys_store"].async_save({"keys": []})

        self._pending_commands.append({"operation": "clear_keys"})
        _LOGGER.info("Clear all keys queued")