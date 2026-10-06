"""Sensor platform for IronLogic."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IronLogic sensors."""
    _LOGGER.debug("Setting up IronLogic sensors")
    data = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        IronLogicWebhookSensor(entry),
        IronLogicLastEventSensor(entry, data),
        IronLogicLastKeySensor(entry, data),
        IronLogicSerialNumberSensor(entry, data),
        IronLogicAllowedKeysSensor(entry, data),
    ]
    async_add_entities(sensors)
    _LOGGER.debug("IronLogic sensors added: %d", len(sensors))


class IronLogicWebhookSensor(SensorEntity):
    """Sensor showing webhook path with copy-friendly attributes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:webhook"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "webhook_url"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._path = f"/api/webhook/{entry.entry_id}"
        self._attr_unique_id = f"{entry.entry_id}_webhook_url"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["host"])},
        )
        self._attr_native_value = "Click to copy"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for the sensor."""
        return {
            "path": self._path,
            "entry_id": self._entry.entry_id,
            "full_url": f"http://HA_IP:8123{self._path}",
        }


class IronLogicLastEventSensor(SensorEntity):
    """Sensor for last door event."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_translation_key = "last_event"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_last_event"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._unsub = None
        self._availability_sub = None
        self._controller_available = True
        self._last_event_code = None
        self._last_key = None
        self._last_key_name = None
        self._attr_native_value = "Waiting for events..."

    def _get_event_description(self, event_code: int) -> str:
        """Get event description."""
        descriptions = {
            0x00: "Opened by internal button",
            0x01: "Opened by internal button (exit)",
            0x02: "Key not found",
            0x03: "Key not found (exit)",
            0x04: "Key granted (entry)",
            0x05: "Key granted (exit)",
            0x06: "Key denied (entry)",
            0x07: "Key denied (exit)",
            0x08: "Opened remotely (exit)",
            0x09: "Opened remotely (entry)",
            0x0A: "Door locked - key denied",
            0x0B: "Door locked - key denied (exit)",
            0x0C: "Door tampered (opened)",
            0x0D: "Door tampered (exit)",
            0x0E: "Door left open (timeout)",
            0x0F: "Door left open (exit)",
            0x10: "Passage completed",
            0x11: "Passage completed (exit)",
            0x20: "Door opened",
            0x21: "Door opened (exit)",
            0x22: "Door closed",
            0x23: "Door closed (exit)",
            0x28: "Passage not completed",
            0x29: "Passage not completed (exit)",
        }
        return descriptions.get(event_code, f"Event {event_code}")

    def _update_state(self):
        """Update state with current values."""
        if self._last_event_code is None:
            self._attr_native_value = "Waiting for events..."
        else:
            desc = self._get_event_description(self._last_event_code)
            event_code = self._last_event_code
            key = self._last_key
            key_name = self._last_key_name

            if event_code in (0x0C, 0x0D, 0x20, 0x21, 0x22, 0x23, 0x0E, 0x0F):
                self._attr_native_value = desc

            elif event_code in (0x02, 0x03, 0x06, 0x07):
                if key and key != "000000000000":
                    formatted = key[-8:] if len(key) > 8 else key
                    self._attr_native_value = f"{desc}: {formatted}"
                else:
                    self._attr_native_value = desc

            elif event_code in (0x04, 0x05):
                if key_name:
                    self._attr_native_value = f"{desc}: {key_name}"
                elif key and key != "000000000000":
                    formatted = key[-8:] if len(key) > 8 else key
                    self._attr_native_value = f"{desc}: {formatted}"
                else:
                    self._attr_native_value = desc

            else:
                self._attr_native_value = desc

    @property
    def available(self) -> bool:
        """Return if sensor is available (controller must be reachable)."""
        return self._controller_available

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self._unsub = self.hass.bus.async_listen(
            f"{DOMAIN}_update_sensor", self._handle_update
        )
        self._availability_sub = self.hass.bus.async_listen(
            f"{DOMAIN}_availability_updated", self._handle_availability_update
        )
        self._update_state()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Remove callbacks."""
        if self._unsub:
            self._unsub()
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

    @callback
    def _handle_update(self, event):
        """Handle sensor update event."""
        if event.data.get("type") != "last_event":
            return
        _LOGGER.debug("LastEvent sensor received event: %s", event.data)
        self._last_event_code = event.data.get("event_code")
        self._last_key = event.data.get("key")
        self._last_key_name = event.data.get("key_name")
        self._update_state()
        self.async_write_ha_state()


class IronLogicLastKeySensor(SensorEntity):
    """Sensor for last key used."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:key"
    _attr_translation_key = "last_key"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_last_key"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._unsub = None
        self._availability_sub = None
        self._controller_available = True
        self._last_key = None
        self._last_key_name = None
        self._last_event_code = None
        self._attr_native_value = "No keys yet"

    def _update_state(self):
        """Update display with current values."""
        if self._last_event_code is None:
            self._attr_native_value = "No keys yet"
        else:
            self._attr_native_value = self._format_key(
                self._last_key, self._last_key_name, self._last_event_code
            )

    def _format_key(
        self, key: str, key_name: str = None, event_code: int = None
    ) -> str:
        """Format key."""
        if event_code in (0x08, 0x09):
            return "Network"

        if event_code in (0x0C, 0x0D, 0x20, 0x21, 0x22, 0x23, 0x0E, 0x0F):
            return self._attr_native_value

        if key and len(key) > 8:
            formatted = key[-8:]
        else:
            formatted = key

        if event_code in (0x02, 0x03, 0x06, 0x07):
            if key and key != "000000000000":
                if event_code in (0x02, 0x03):
                    status = "not found"
                else:
                    status = "denied"
                return f"{formatted} ({status})"
            return "Unknown key"

        if event_code in (0x04, 0x05):
            if key_name and key_name not in ("Unknown", "Unknown key"):
                return f"{key_name} ({formatted})"
            elif key and key != "000000000000":
                return f"{formatted} (granted)"
            return "No keys yet"

        if key_name and key_name not in ("Unknown", "Unknown key"):
            return f"{key_name} ({formatted})"
        elif key and key != "000000000000":
            return formatted
        return "No keys yet"

    @property
    def available(self) -> bool:
        """Return if sensor is available (controller must be reachable)."""
        return self._controller_available

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self._unsub = self.hass.bus.async_listen(
            f"{DOMAIN}_update_sensor", self._handle_update
        )
        self._availability_sub = self.hass.bus.async_listen(
            f"{DOMAIN}_availability_updated", self._handle_availability_update
        )
        self._update_state()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Remove callbacks."""
        if self._unsub:
            self._unsub()
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

    @callback
    def _handle_update(self, event):
        """Handle sensor update event."""
        if event.data.get("type") != "last_key":
            return
        _LOGGER.debug("LastKey sensor received event: %s", event.data)
        self._last_key = event.data.get("key")
        self._last_key_name = event.data.get("key_name")
        self._last_event_code = event.data.get("event_code")
        self._update_state()
        self.async_write_ha_state()


class IronLogicSerialNumberSensor(SensorEntity):
    """Sensor for controller serial number."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:identifier"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "serial_number"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_sn"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._unsub = None
        self._availability_sub = None
        self._controller_available = True
        self._sn = data.get("sn")
        self._attr_native_value = self._sn or "Waiting for data..."

    @property
    def available(self) -> bool:
        """Return if sensor is available (controller must be reachable)."""
        return self._controller_available

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self._unsub = self.hass.bus.async_listen(
            f"{DOMAIN}_sn_updated", self._handle_sn_update
        )
        self._availability_sub = self.hass.bus.async_listen(
            f"{DOMAIN}_availability_updated", self._handle_availability_update
        )
        if self._data.get("sn"):
            self._sn = self._data.get("sn")
            self._attr_native_value = self._sn
        else:
            self._attr_native_value = "Waiting for data..."
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Remove callbacks."""
        if self._unsub:
            self._unsub()
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

    @callback
    def _handle_sn_update(self, event):
        """Handle SN update event."""
        sn = event.data.get("sn")
        _LOGGER.debug("SN sensor received update: %s", sn)
        if sn and sn != self._sn:
            self._sn = sn
            self._attr_native_value = sn
            self.async_write_ha_state()
            _LOGGER.debug("Serial number updated to: %s", sn)


class IronLogicAllowedKeysSensor(SensorEntity):
    """Sensor showing allowed keys count with list in attributes."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-key"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "allowed_keys"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_allowed_keys"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._unsub = None
        self._keys_sub = None
        self._controller_available = True
        self._update_value()

    def _update_value(self):
        """Update sensor value."""
        keys = self._data.get("keys", [])
        normalized = []
        for k in keys:
            if isinstance(k, str):
                import json
                try:
                    k = json.loads(k)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(k, dict):
                normalized.append(k)
        self._attr_native_value = len(normalized)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        keys = self._data.get("keys", [])
        normalized = []
        for k in keys:
            if isinstance(k, str):
                import json
                try:
                    k = json.loads(k)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(k, dict):
                normalized.append({
                    "key_number": k.get("key_number", ""),
                    "name": k.get("name", ""),
                    "type": k.get("type", "normal"),
                    "added_at": k.get("added_at"),
                    "last_used": k.get("last_used"),
                })
        return {
            "keys": normalized,
            "count": len(normalized),
        }

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._controller_available

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()
        self._unsub = self.hass.bus.async_listen(
            f"{DOMAIN}_availability_updated", self._handle_availability_update
        )
        self._keys_sub = self.hass.bus.async_listen(
            f"{DOMAIN}_keys_updated", self._handle_keys_update
        )
        self._update_value()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Remove callbacks."""
        if self._unsub:
            self._unsub()
        if self._keys_sub:
            self._keys_sub()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_availability_update(self, event):
        """Handle availability change."""
        available = event.data.get("available", False)
        if self._controller_available != available:
            self._controller_available = available
            self.async_write_ha_state()

    @callback
    def _handle_keys_update(self, event):
        """Handle keys list update."""
        self._update_value()
        self.async_write_ha_state()