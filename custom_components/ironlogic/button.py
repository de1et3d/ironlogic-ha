"""Button platform for IronLogic."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
        """Return if button is available (controller must be reachable)."""
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

        _LOGGER.info("Rebooting controller %s", self._data["host"])
        success = await self._api.reboot()

        if success:
            _LOGGER.info("Controller reboot command sent successfully")
        else:
            _LOGGER.error("Failed to send reboot command to controller")


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
        """Return if button is available (controller must be reachable)."""
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

        # Get local network URL (the one HA uses internally)
        ha_url = get_url(self.hass, prefer_external=False, allow_cloud=False)
        _LOGGER.debug("Local URL from HA: %s", ha_url)
        
        # Force HTTP and port 8123
        # Replace https with http
        ha_url = ha_url.replace('https://', 'http://')
        
        # Extract hostname (domain or IP)
        from urllib.parse import urlparse
        parsed = urlparse(ha_url)
        host = parsed.hostname
        
        if not host:
            _LOGGER.error("Could not extract hostname from %s", ha_url)
            return
        
        # Build webhook URL with HTTP on port 8123
        webhook_url = f"http://{host}:8123/api/webhook/{self._entry.entry_id}"
        
        _LOGGER.info("Setting webhook URL: %s", webhook_url)
        success = await self._api.set_webhook_url(webhook_url)

        if success:
            _LOGGER.info("Webhook URL set successfully")
            self.hass.bus.async_fire(f"{DOMAIN}_webhook_configured", {"url": webhook_url})
        else:
            _LOGGER.error("Failed to set webhook URL")