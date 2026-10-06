"""Button platform for IronLogic IP Controller."""

import asyncio
import csv
import logging
from pathlib import Path

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url

from .const import DOMAIN, CONNECTION_TYPE_WEBSOCKET

_LOGGER = logging.getLogger(__name__)

DEFAULT_EXPORT_PATH = "/config/ironlogic_keys_export.csv"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IronLogic button controls."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]

    buttons = [
        IronLogicRebootButton(entry, data, api),
        IronLogicSetWebhookButton(entry, data, api),
        IronLogicExportKeysButton(entry, data),
    ]
    async_add_entities(buttons)


class IronLogicRebootButton(ButtonEntity):
    """Button to reboot the controller."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:restart"
    _attr_translation_key = "reboot"
    _attr_name = "Reboot controller"

    def __init__(self, entry: ConfigEntry, data: dict, api) -> None:
        """Initialize the button."""
        self._entry = entry
        self._data = data
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_reboot"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._controller_available = True
        self._availability_sub = None

    @property
    def available(self) -> bool:
        """Return if button is available."""
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

    async def _handle_availability_update(self, event):
        """Handle availability change."""
        available = event.data.get("available", False)
        if self._controller_available != available:
            self._controller_available = available
            self.async_write_ha_state()

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self._controller_available:
            _LOGGER.warning("Cannot reboot - controller is unavailable")
            return

        _LOGGER.warning("Rebooting controller %s", self._data["host"])
        success = await self._api.reboot()

        if success:
            _LOGGER.warning("Controller reboot command sent successfully")
        else:
            _LOGGER.warning("Failed to send reboot command to controller")


class IronLogicSetWebhookButton(ButtonEntity):
    """Button to set webhook URL in controller."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:webhook"
    _attr_translation_key = "set_webhook"
    _attr_name = "Set webhook URL"

    def __init__(self, entry: ConfigEntry, data: dict, api) -> None:
        """Initialize the button."""
        self._entry = entry
        self._data = data
        self._api = api
        self._attr_unique_id = f"{entry.entry_id}_set_webhook"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )
        self._controller_available = True
        self._availability_sub = None

    @property
    def available(self) -> bool:
        """Return if button is available."""
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

    async def _handle_availability_update(self, event):
        """Handle availability change."""
        available = event.data.get("available", False)
        if self._controller_available != available:
            self._controller_available = available
            self.async_write_ha_state()

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self._controller_available:
            _LOGGER.warning("Cannot set webhook - controller is unavailable")
            return

        ha_url = get_url(self.hass, prefer_external=False, allow_cloud=False)
        _LOGGER.debug("Local URL from HA: %s", ha_url)

        ha_url = ha_url.replace("https://", "http://")

        from urllib.parse import urlparse

        parsed = urlparse(ha_url)
        host = parsed.hostname

        if not host:
            _LOGGER.warning("Could not extract hostname from %s", ha_url)
            return

        base_url = f"http://{host}:8123"
        webhook_path = f"/api/webhook/{self._entry.entry_id}"

        connection_type = self._data.get("connection_type")

        if connection_type == CONNECTION_TYPE_WEBSOCKET:
            webhook_url = f"ws://{host}:8124{webhook_path}"
        else:
            webhook_url = base_url + webhook_path

        _LOGGER.warning(
            "Setting webhook URL: %s (connection_type=%s)",
            webhook_url,
            connection_type,
        )
        success = await self._api.set_webhook_url(
            webhook_url, period=10, connection_type=connection_type
        )

        if success:
            _LOGGER.warning("Webhook URL set successfully")
            self.hass.bus.async_fire(
                f"{DOMAIN}_webhook_configured", {"url": webhook_url}
            )

            _LOGGER.warning("Waiting 5 seconds before reboot...")
            await asyncio.sleep(5)

            _LOGGER.warning("Rebooting controller...")
            await self._api.reboot()
            _LOGGER.warning("Controller reboot initiated")
        else:
            _LOGGER.warning("Failed to set webhook URL")


class IronLogicExportKeysButton(ButtonEntity):
    """Button to export allowed keys to CSV."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:content-save"
    _attr_translation_key = "export_keys"
    _attr_name = "Export keys"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        """Initialize the button."""
        self._entry = entry
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_export_keys"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data["host"])},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.warning("Exporting keys to %s", DEFAULT_EXPORT_PATH)
        success = await export_keys_to_csv(
            self.hass, self._data, DEFAULT_EXPORT_PATH
        )
        if success:
            _LOGGER.warning("Keys export completed")
        else:
            _LOGGER.warning("Keys export failed")
        self.hass.bus.async_fire(
            f"{DOMAIN}_keys_exported", {"file_path": DEFAULT_EXPORT_PATH}
        )


def _write_keys_csv(file_path: str, normalized: list) -> int:
    """Write keys to CSV (blocking, runs in executor)."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["key_number", "name", "type", "added_at", "last_used"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for key in normalized:
            writer.writerow({
                "key_number": key.get("key_number", ""),
                "name": key.get("name", ""),
                "type": key.get("type", "normal"),
                "added_at": key.get("added_at", ""),
                "last_used": key.get("last_used", ""),
            })

    return len(normalized)


async def export_keys_to_csv(
    hass: HomeAssistant, data: dict, file_path: str
) -> bool:
    """Export keys list to CSV file."""
    keys = data.get("keys", [])

    normalized = []
    for k in keys:
        if isinstance(k, str):
            import json

            try:
                k = json.loads(k)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(k, dict) and k.get("key_number"):
            normalized.append(k)

    if not normalized:
        _LOGGER.warning("No keys to export")
        return False

    try:
        count = await hass.async_add_executor_job(
            _write_keys_csv, file_path, normalized
        )
        _LOGGER.warning("Exported %d keys to %s", count, file_path)
        return True

    except Exception as e:
        _LOGGER.warning("Failed to export keys: %s", e)
        return False