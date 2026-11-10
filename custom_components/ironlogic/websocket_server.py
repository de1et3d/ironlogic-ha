"""WebSocket server for IronLogic IP Controller."""

import asyncio
import json
import logging
from typing import Any, Optional
from datetime import datetime

from aiohttp import web, WSMsgType

from .keys import is_key_allowed, build_sync_commands

_LOGGER = logging.getLogger(__name__)

SYNC_BATCH_SIZE = 50
DEFAULT_WS_PORT = 8124


class IronLogicWebSocketHandler:
    """Handle WebSocket connection for a single controller entry."""

    def __init__(self, hass, entry_id: str, entry_data: dict[str, Any]) -> None:
        """Initialize handler for specific entry."""
        self.hass = hass
        self.entry_id = entry_id
        self.entry_data = entry_data
        self._ws: Optional[web.WebSocketResponse] = None
        self._pending_commands = []
        self._message_id = 0
        self._active = False
        self._keys_version = 0
        self._synced_keys_version = 0

    @property
    def active(self) -> bool:
        return self._active

    @property
    def ws(self) -> Optional[web.WebSocketResponse]:
        return self._ws

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection for this entry."""
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        self._ws = ws
        _LOGGER.info("Controller connected via WebSocket to %s (entry %s)", request.path, self.entry_id)
        self._active = True

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        _LOGGER.debug("WebSocket received for %s: %s", self.entry_id, data)
                        response = await self._process_message(data)
                        if response and not ws.closed:
                            try:
                                await ws.send_str(json.dumps(response))
                            except Exception as err:
                                _LOGGER.debug("Failed to send response for %s: %s", self.entry_id, err)
                                break
                    except json.JSONDecodeError:
                        _LOGGER.error("Failed to decode JSON for %s: %s", self.entry_id, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error for %s: %s", self.entry_id, ws.exception())
                elif msg.type == WSMsgType.CLOSE:
                    _LOGGER.info("WebSocket connection closed by controller for %s", self.entry_id)
                    break
        except Exception as err:
            _LOGGER.debug("WebSocket handler error for %s: %s", self.entry_id, err)
        finally:
            self._ws = None
            self._active = False

        return ws

    async def _process_message(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Process incoming WebSocket message and return response."""
        from .const import CONF_SN

        messages = data.get("messages", [])
        global_sn = data.get(CONF_SN)
        global_type = data.get("type")

        responses = []
        deferred_commands = []

        for message in messages:
            operation = message.get("operation")
            msg_id = message.get("id")

            if message.get("success") == 1:
                _LOGGER.debug("Received success confirmation for id %d", msg_id)
                continue

            if "cards" in message:
                await self._handle_keys(message)
                responses.append({"id": msg_id, "success": 1})
            elif operation == "power_on":
                await self._handle_power_on(message, global_sn, global_type)
                responses.append({
                    "id": msg_id + 1,
                    "operation": "set_active",
                    "active": 1,
                    "online": 1,
                })
                deferred_commands.extend(self._build_sync_commands(msg_id + 2))
            elif operation == "check_access":
                key_id = message.get("card", "")
                reader = message.get("reader", 1)
                granted = self._is_key_allowed(key_id)
                _LOGGER.debug(
                    "Access check for key %s on reader %d: %s",
                    key_id,
                    reader,
                    "GRANTED" if granted else "DENIED",
                )
                responses.append({
                    "id": msg_id,
                    "operation": "check_access",
                    "granted": granted,
                })

                if self._keys_version > self._synced_keys_version:
                    _LOGGER.debug("Keys out of sync detected during check_access, will re-sync on next ping")
            elif operation == "events":
                response = await self._handle_events(message)
                if response:
                    responses.append(response)
            elif operation == "ping":
                commands = await self._get_pending_commands()

                if self._keys_version > self._synced_keys_version:
                    sync_cmds = self._build_sync_commands(self._message_id + 1)
                    for cmd in sync_cmds:
                        self._message_id += 1
                        cmd["id"] = self._message_id
                    commands.extend(sync_cmds)
                    self._synced_keys_version = self._keys_version
                    _LOGGER.info("Keys out of sync for %s, sending %d sync commands", self.entry_id, len(sync_cmds))

                if commands:
                    return {
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "interval": 10,
                        "messages": commands,
                    }
            else:
                _LOGGER.debug("Unhandled operation for %s: %s", self.entry_id, operation)

        all_responses = responses + deferred_commands

        if all_responses:
            return {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "interval": 10,
                "messages": all_responses,
            }
        return None

    def _is_key_allowed(self, key_id: str) -> int:
        """Check if key is allowed."""
        return is_key_allowed(key_id, self.entry_data.get("keys", []))

    def increment_keys_version(self) -> None:
        """Increment keys version to trigger re-sync."""
        self._keys_version += 1
        _LOGGER.debug("Keys version incremented to %d for %s", self._keys_version, self.entry_id)

    def _build_sync_commands(self, start_id: int) -> list:
        """Build commands to sync allowed keys to controller."""
        return build_sync_commands(self.entry_data.get("keys", []), start_id, SYNC_BATCH_SIZE)

    async def _handle_power_on(
        self, message: dict, global_sn: str, global_type: str
    ) -> None:
        """Handle power_on message."""
        from . import DOMAIN, get_model_from_type
        from homeassistant.helpers import device_registry as dr

        sn = message.get("sn") or global_sn or "unknown"
        controller_type = message.get("type") or global_type or "unknown"
        _LOGGER.info(
            "Controller %s (%s) powered on via WebSocket for entry %s", sn, controller_type, self.entry_id
        )

        model = get_model_from_type(controller_type)
        current_sn = self.entry_data.get(CONF_SN)
        current_model = self.entry_data.get(CONF_MODEL)
        need_update = False

        if sn != "unknown" and current_sn != sn:
            self.entry_data[CONF_SN] = sn
            need_update = True
            self.hass.bus.async_fire(f"{DOMAIN}_sn_updated", {"sn": sn})

        if current_model != model:
            self.entry_data[CONF_MODEL] = model
            need_update = True

        if need_update:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                new_data = {**entry.data, CONF_SN: sn, CONF_MODEL: model}
                self.hass.config_entries.async_update_entry(entry, data=new_data)

            new_name = f"IronLogic {model} ({sn} @ {self.entry_data['host']})"
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device(
                identifiers={(DOMAIN, self.entry_data["host"])}
            )
            if device:
                device_registry.async_update_device(device.id, name=new_name)

            if entry:
                self.hass.config_entries.async_update_entry(entry, title=new_name)

        self._keys_version += 1
        _LOGGER.debug("Keys version incremented to %d after power_on for %s, will re-sync on next ping", self._keys_version, self.entry_id)

    async def _handle_events(self, message: dict) -> Optional[dict]:
        """Handle events message."""
        events = message.get("events", [])
        last_event = message.get("last_event", 0)
        msg_id = message.get("id")

        await self._process_events(events)

        return {
            "id": msg_id,
            "operation": "events",
            "events_success": last_event if last_event > 0 else len(events),
        }

    async def _process_events(self, events: list) -> None:
        """Process events."""
        from . import DOMAIN, DOOR_OPEN_EVENTS, DOOR_CLOSED_EVENTS
        from . import EVENT_KEY_GRANTED, EVENT_KEY_GRANTED_EXIT
        from . import EVENT_KEY_NOT_FOUND, EVENT_KEY_NOT_FOUND_EXIT
        from . import EVENT_KEY_DENIED, EVENT_KEY_DENIED_EXIT
        from . import EVENT_OPENED_BY_NETWORK, EVENT_OPENED_BY_NETWORK_EXIT
        from . import EVENT_DOOR_LEFT_OPEN, EVENT_DOOR_LEFT_OPEN_EXIT

        use_door_sensor = self.entry_data.get("use_door_sensor", False)
        door_sensor = self.entry_data.get("door_sensor_entity")

        for event in events:
            if not isinstance(event, dict):
                continue

            event_code = event.get("event")
            key_id = event.get("card")
            _LOGGER.debug("Event code=%s, key=%s for %s", event_code, key_id, self.entry_id)

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

            if event_code in DOOR_OPEN_EVENTS:
                if use_door_sensor and door_sensor:
                    door_sensor.update_state(True)
                self.hass.bus.async_fire(
                    f"{DOMAIN}_door_opened", {"event_code": event_code}
                )
                self._fire_sensor_update("last_event", event_code, key_id, key_name)

            elif event_code in DOOR_CLOSED_EVENTS:
                if use_door_sensor and door_sensor:
                    door_sensor.update_state(False)
                self.hass.bus.async_fire(
                    f"{DOMAIN}_door_closed", {"event_code": event_code}
                )
                self._fire_sensor_update("last_event", event_code, key_id, key_name)

            elif event_code in (EVENT_KEY_GRANTED, EVENT_KEY_GRANTED_EXIT):
                self.hass.bus.async_fire(
                    f"{DOMAIN}_key_granted",
                    {"key": key_id, "key_name": key_name, "time": event.get("time")},
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

    def _fire_sensor_update(
        self,
        sensor_type: str,
        event_code: int = None,
        key: str = None,
        key_name: str = None,
    ) -> None:
        """Fire sensor update event."""
        from . import DOMAIN

        data = {
            "type": sensor_type,
            "event_code": event_code,
            "key": key,
            "key_name": key_name,
        }
        self.hass.bus.async_fire(f"{DOMAIN}_update_sensor", data)

    async def _handle_keys(self, message: dict) -> None:
        """Handle keys response."""
        from . import DOMAIN

        cards = message.get("cards", [])
        _LOGGER.info(
            "Received %d keys from controller via WebSocket for %s", len(cards), self.entry_id
        )

        keys = []
        for card_item in cards:
            key_data = {
                "key_number": card_item.get("card", ""),
                "name": "",
                "type": "blocking" if card_item.get("flags") == 8 else "normal",
                "flags": card_item.get("flags", 0),
                "added_at": None,
                "last_used": None,
            }
            keys.append(key_data)

        self.entry_data["keys"] = keys
        if self.entry_data.get("keys_store"):
            await self.entry_data["keys_store"].async_save({"keys": keys})

        self._synced_keys_version = self._keys_version

        self.hass.bus.async_fire(f"{DOMAIN}_keys_updated", {"keys": keys})

    async def _get_pending_commands(self) -> list:
        """Get pending commands from locks and clear queue."""
        commands = []

        for lock in self.entry_data.get("locks", {}).values():
            if hasattr(lock, "get_pending_commands"):
                for cmd in lock.get_pending_commands():
                    self._message_id += 1
                    cmd["id"] = self._message_id
                    commands.append(cmd)

        return commands

    async def send_command(self, command: dict) -> bool:
        """Send command to controller."""
        if "id" not in command:
            self._message_id += 1
            command["id"] = self._message_id

        if self._ws and not self._ws.closed and self._active:
            try:
                response = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "interval": 10,
                    "messages": [command],
                }
                await self._ws.send_str(json.dumps(response))
                _LOGGER.debug("Sent to %s: %s", self.entry_id, response)
                return True
            except Exception as e:
                _LOGGER.error("Failed to send command for %s: %s", self.entry_id, e)
                return False
        else:
            _LOGGER.warning("WebSocket not connected for %s, cannot send command", self.entry_id)
            return False

    async def get_pending_commands(self) -> list:
        """Get and clear pending commands."""
        commands = self._pending_commands.copy()
        self._pending_commands.clear()
        return commands


class IronLogicWebSocketServer:
    """Shared WebSocket server for all IronLogic controller entries."""

    _instance: Optional["IronLogicWebSocketServer"] = None

    def __init__(self, hass, port: int = DEFAULT_WS_PORT) -> None:
        """Initialize shared WebSocket server."""
        self.hass = hass
        self._port = port
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._handlers: dict[str, IronLogicWebSocketHandler] = {}
        self._started = False

    @classmethod
    def get_instance(cls, hass, port: int = DEFAULT_WS_PORT) -> "IronLogicWebSocketServer":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(hass, port)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing/reload)."""
        cls._instance = None

    def register_handler(self, entry_id: str, entry_data: dict[str, Any]) -> IronLogicWebSocketHandler:
        """Register a handler for an entry."""
        handler = IronLogicWebSocketHandler(self.hass, entry_id, entry_data)
        self._handlers[entry_id] = handler
        if self._started and self._runner:
            self._runner.app.router.add_get(
                f"/api/webhook/{entry_id}", handler.handle_websocket
            )
        return handler

    def unregister_handler(self, entry_id: str) -> None:
        """Unregister handler for an entry."""
        if entry_id in self._handlers:
            del self._handlers[entry_id]

    async def start(self) -> None:
        """Start shared WebSocket server."""
        if self._started:
            return

        app = web.Application()
        for entry_id, handler in self._handlers.items():
            app.router.add_get(f"/api/webhook/{entry_id}", handler.handle_websocket)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await self._site.start()
        self._started = True
        _LOGGER.info("Shared WebSocket server started on port %s", self._port)

    async def stop(self) -> None:
        """Stop shared WebSocket server."""
        if not self._started:
            return

        for handler in self._handlers.values():
            if handler.ws and not handler.ws.closed:
                try:
                    await handler.ws.close()
                except Exception:
                    pass
            handler._active = False
            handler._ws = None

        if self._runner:
            await self._runner.cleanup()
        self._runner = None
        self._site = None
        self._started = False
        _LOGGER.info("Shared WebSocket server stopped")

    def get_handler(self, entry_id: str) -> Optional[IronLogicWebSocketHandler]:
        """Get handler for entry."""
        return self._handlers.get(entry_id)