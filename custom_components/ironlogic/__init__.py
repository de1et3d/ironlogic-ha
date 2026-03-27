"""Init for IronLogic Z-5R Controller integration."""

import logging
import json
from datetime import datetime, timedelta
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AUTH_KEY,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    PLATFORMS,
    DEFAULT_POLL_INTERVAL,
    EVENT_KEY_NOT_FOUND,
    EVENT_KEY_NOT_FOUND_EXIT,
    EVENT_KEY_GRANTED,
    EVENT_KEY_GRANTED_EXIT,
    EVENT_KEY_DENIED,
    EVENT_KEY_DENIED_EXIT,
    EVENT_OPENED_BY_NETWORK,
    EVENT_OPENED_BY_NETWORK_EXIT,
    EVENT_DOOR_LEFT_OPEN,
    EVENT_DOOR_LEFT_OPEN_EXIT,
    DOOR_OPEN_EVENTS,
    DOOR_CLOSED_EVENTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IronLogic Z-5R from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    auth_key = entry.data[CONF_AUTH_KEY]

    from .api import IronLogicAPI

    api = IronLogicAPI(host, username, auth_key)

    # Load stored keys from persistent storage
    keys_store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
    keys_data = await keys_store.async_load() or {}
    keys = keys_data.get("keys", [])

    # Get settings from entry data
    use_door_sensor = entry.data.get("use_door_sensor", False)
    poll_interval = entry.data.get("poll_interval", DEFAULT_POLL_INTERVAL)
    sn = entry.data.get("sn", None)

    # Create availability coordinator
    async def async_update_availability():
        try:
            return await api.check_availability()
        except Exception as err:
            _LOGGER.debug("Availability check failed: %s", err)
            return False

    availability_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"IronLogic Availability {host}",
        update_method=async_update_availability,
        update_interval=timedelta(seconds=poll_interval),
    )
    await availability_coordinator.async_config_entry_first_refresh()

    entry_data = {
        "api": api,
        "host": host,
        "username": username,
        "auth_key": auth_key,
        "locks": {},
        "keys": keys,
        "keys_store": keys_store,
        "availability_coordinator": availability_coordinator,
        "use_door_sensor": use_door_sensor,
        "poll_interval": poll_interval,
        "sn": sn,
        "door_sensor_entity": None,
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    hass.http.register_view(IronLogicWebhookView(hass, entry.entry_id, entry_data))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Create device name (initially with IP only, will be updated when SN received)
    device_name = f"IronLogic Z-5R ({host})"

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, host)},
        name=device_name,
        manufacturer="IronLogic",
        model="Z-5R",
    )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload IronLogic integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload IronLogic config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].get(entry.entry_id)
        if data and data.get("keys_store"):
            await data["keys_store"].async_save({"keys": data.get("keys", [])})
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_entry_data(hass: HomeAssistant, entry_id: str, **kwargs) -> None:
    """Update entry data without full reload (for controls)."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry:
        new_data = {**entry.data, **kwargs}
        hass.config_entries.async_update_entry(entry, data=new_data)
        # Update in-memory data
        data = hass.data[DOMAIN].get(entry_id)
        if data:
            for key, value in kwargs.items():
                data[key] = value


class IronLogicWebhookView(HomeAssistantView):
    """Handle webhook from IronLogic controller."""

    requires_auth = False

    def __init__(self, hass: HomeAssistant, entry_id: str, entry_data: dict[str, Any]):
        self.hass = hass
        self.entry_id = entry_id
        self.entry_data = entry_data
        self.url = f"/api/webhook/{entry_id}"
        self.name = f"api:webhook:{entry_id}"

    async def get(self, request):
        response = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interval": 10,
            "messages": [],
        }
        return self._json_response(response)

    async def post(self, request):
        try:
            data = await request.json()
            _LOGGER.debug("Received data from controller: %s", data)

            response = await self._process_message(data)
            return self._json_response(response)

        except Exception as err:
            _LOGGER.error("Webhook error: %s", err, exc_info=True)
            return self._json_response({"error": "Internal error"}, 500)

    async def _process_message(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process message from controller."""
        messages = data.get("messages", [])
        responses = []

        # Get global SN if present
        global_sn = data.get("sn")

        for message in messages:
            msg_id = message.get("id")
            operation = message.get("operation")

            if message.get("success") == 1:
                _LOGGER.debug("Received success confirmation for id %d", msg_id)
                continue

            if operation == "power_on":
                # Pass global_sn to handler
                response = await self._handle_power_on(msg_id, message, global_sn)
            elif operation == "check_access":
                response = await self._handle_check_access(msg_id, message)
            elif operation == "ping":
                response = await self._handle_ping(msg_id, message)
            elif operation == "events":
                response = await self._handle_events(msg_id, message)
            else:
                response = {"id": msg_id, "success": 0, "error": "Unknown operation"}

            if response is not None:
                responses.append(response)

        return {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interval": 10,
            "messages": responses,
        }

    async def _handle_power_on(
        self, msg_id: int, message: dict[str, Any], global_sn: str = None
    ) -> dict[str, Any]:
        """Handle controller power-on event."""
        sn = message.get("sn") or global_sn or "unknown"
        _LOGGER.info("Controller %s powered on", sn)

        current_sn = self.entry_data.get("sn")
        need_update = False
        need_sn_event = False

        if sn != "unknown" and current_sn != sn:
            _LOGGER.debug("Saving new SN %s, current SN: %s", sn, current_sn)
            self.entry_data["sn"] = sn
            need_update = True
            need_sn_event = True
        elif sn != "unknown" and current_sn == sn:
            # Check if device name needs update
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.entry_data["host"])}
            )
            expected_name = f"IronLogic Z-5R ({sn} @ {self.entry_data['host']})"
            if device and device.name != expected_name:
                _LOGGER.debug(
                    "Device name needs update: current='%s', expected='%s'",
                    device.name,
                    expected_name,
                )
                need_update = True
            else:
                _LOGGER.debug("SN already saved and device name is correct")

        if need_update:
            # Update entry data with SN if not already set
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry and self.entry_data.get("sn") != sn:
                new_data = {**entry.data, "sn": sn}
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.debug("Entry data updated with SN")

            # Format new name with SN and IP
            new_name = f"IronLogic Z-5R ({sn} @ {self.entry_data['host']})"
            _LOGGER.debug("New name will be: %s", new_name)

            # Update device name in registry
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.entry_data["host"])}
            )
            if device:
                _LOGGER.debug(
                    "Found device with id: %s, current name: %s", device.id, device.name
                )
                device_registry.async_update_device(device.id, name=new_name)
                _LOGGER.debug("Device name updated to: %s", new_name)
            else:
                _LOGGER.warning(
                    "Device not found in registry for host: %s", self.entry_data["host"]
                )

            # Update entry title
            if entry:
                self.hass.config_entries.async_update_entry(entry, title=new_name)
                _LOGGER.debug("Entry title updated to: %s", new_name)

        # Always fire SN event if we have SN and sensor needs update
        if sn != "unknown" and (need_sn_event or self.entry_data.get("sn") == sn):
            self.hass.bus.async_fire(f"{DOMAIN}_sn_updated", {"sn": sn})
            _LOGGER.debug("SN update event fired")

        return {
            "id": msg_id + 1,
            "operation": "set_active",
            "active": 1,
            "online": 0,
        }

    async def _handle_check_access(
        self, msg_id: int, message: dict[str, Any]
    ) -> dict[str, Any]:
        key = message.get("card", "")
        reader = message.get("reader", 1)
        _LOGGER.debug("Access check for key %s on reader %d", key, reader)
        return {
            "id": msg_id,
            "operation": "check_access",
            "granted": 1,
        }

    async def _handle_ping(
        self, msg_id: int, message: dict[str, Any]
    ) -> dict[str, Any]:
        commands = await self._get_pending_commands()
        if commands:
            response_commands = []
            for i, cmd in enumerate(commands):
                cmd_copy = cmd.copy()
                cmd_copy["id"] = msg_id + i + 1
                response_commands.append(cmd_copy)
            return {"id": msg_id, "messages": response_commands}
        return None

    async def _get_pending_commands(self) -> list[dict[str, Any]]:
        commands = []
        for lock in self.entry_data.get("locks", {}).values():
            if hasattr(lock, "get_pending_commands"):
                commands.extend(lock.get_pending_commands())
        return commands

    async def _handle_events(
        self, msg_id: int, message: dict[str, Any]
    ) -> dict[str, Any]:
        events = message.get("events", [])
        last_event = message.get("last_event", 0)

        await self._process_events(events)

        events_success = last_event if last_event > 0 else len(events)
        _LOGGER.debug("Sending events_success=%d", events_success)

        return {"id": msg_id, "operation": "events", "events_success": events_success}

    async def _process_events(self, events: list[dict[str, Any]]) -> None:
        """Process controller events and update lock state."""
        use_door_sensor = self.entry_data.get("use_door_sensor", False)
        door_sensor = self.entry_data.get("door_sensor_entity")

        for event in events:
            if not isinstance(event, dict):
                continue

            event_code = event.get("event")
            key_id = event.get("card")
            flags = event.get("flag", 0)
            _LOGGER.debug("Event code=%s, key=%s, flags=%s", event_code, key_id, flags)

            # Find key name if exists
            key_name = None
            raw_keys = self.entry_data.get("keys", [])
            normalized_keys = []
            for k in raw_keys:
                if isinstance(k, str):
                    try:
                        k = json.loads(k)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(k, dict):
                    normalized_keys.append(k)

            for k in normalized_keys:
                if k.get("key_number") == key_id:
                    key_name = k.get("name")
                    k["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if self.entry_data.get("keys_store"):
                        await self.entry_data["keys_store"].async_save(
                            {"keys": normalized_keys}
                        )
                    break

            # Handle door state events (only if door sensor is enabled)
            if event_code in DOOR_OPEN_EVENTS:
                if use_door_sensor:
                    if door_sensor:
                        door_sensor.update_state(True)
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_door_opened", {"event_code": event_code}
                    )
                    self._fire_sensor_update("last_event", event_code, key_id, key_name)
                # else: ignore door events completely

            elif event_code in DOOR_CLOSED_EVENTS:
                if use_door_sensor:
                    if door_sensor:
                        door_sensor.update_state(False)
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_door_closed", {"event_code": event_code}
                    )
                    self._fire_sensor_update("last_event", event_code, key_id, key_name)
                # else: ignore door events completely

            elif event_code in (EVENT_KEY_GRANTED, EVENT_KEY_GRANTED_EXIT):
                self.hass.bus.async_fire(
                    f"{DOMAIN}_key_granted",
                    {
                        "key": key_id,
                        "key_name": key_name,
                        "time": event.get("time"),
                    },
                )
                self._fire_sensor_update("last_event", event_code, key_id, key_name)
                if key_id:
                    self._fire_sensor_update("last_key", event_code, key_id, key_name)

            elif event_code in (
                EVENT_KEY_NOT_FOUND,
                EVENT_KEY_NOT_FOUND_EXIT,
                EVENT_KEY_DENIED,
                EVENT_KEY_DENIED_EXIT,
            ):
                _LOGGER.debug(
                    "DENIED/NOT_FOUND event: event_code=%s, key=%s", event_code, key_id
                )
                self.hass.bus.async_fire(
                    f"{DOMAIN}_key_denied",
                    {
                        "key": key_id,
                        "key_name": key_name or "Unknown key",
                        "time": event.get("time"),
                    },
                )
                self._fire_sensor_update("last_event", event_code, key_id, key_name)
                self._fire_sensor_update(
                    "last_key", event_code, key_id, key_name or "Unknown"
                )

            elif event_code in (EVENT_OPENED_BY_NETWORK, EVENT_OPENED_BY_NETWORK_EXIT):
                self.hass.bus.async_fire(f"{DOMAIN}_door_opened_remotely", {})
                self._fire_sensor_update("last_event", event_code, None, None)
                self._fire_sensor_update("last_key", event_code, None, None)

            elif event_code in (EVENT_DOOR_LEFT_OPEN, EVENT_DOOR_LEFT_OPEN_EXIT):
                if use_door_sensor:
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_door_left_open", {"event_code": event_code}
                    )
                    self._fire_sensor_update("last_event", event_code, key_id, key_name)
                # else: ignore

    def _fire_sensor_update(
        self,
        sensor_type: str,
        event_code: int = None,
        key: str = None,
        key_name: str = None,
    ) -> None:
        data = {
            "type": sensor_type,
            "event_code": event_code,
            "key": key,
            "key_name": key_name,
        }
        _LOGGER.debug("Firing sensor update: %s", data)
        self.hass.bus.async_fire(f"{DOMAIN}_update_sensor", data)

    def _json_response(self, data: dict[str, Any], status: int = 200):
        import json

        return web.Response(
            text=json.dumps(data), content_type="application/json", status=status
        )