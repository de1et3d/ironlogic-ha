"""Options flow for IronLogic IP Controller."""

import json
import logging
import time
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    DOMAIN,
    CONF_CONNECTION_TYPE,
    CONNECTION_TYPE_HTTP,
    CONNECTION_TYPE_WEBSOCKET,
)
from .keys import normalize_key_number, short_key_number

_LOGGER = logging.getLogger(__name__)


class IronLogicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for IronLogic IP Controller."""

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        self.data = self.hass.data[DOMAIN][self.config_entry.entry_id]
        self.keys = self.data.get("keys", [])

        coordinator = self.data.get("availability_coordinator")
        is_available = coordinator.data if coordinator else False

        if not is_available:
            return await self.async_step_offline()

        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "allowed_keys"],
        )

    async def async_step_general(self, user_input=None):
        """General settings."""
        if user_input is not None:
            new_data = {**self.config_entry.data}

            if user_input.get("connection_type"):
                new_data[CONF_CONNECTION_TYPE] = user_input["connection_type"]

            if user_input.get("poll_interval"):
                new_data["poll_interval"] = user_input["poll_interval"]

            if user_input.get("use_door_sensor") is not None:
                new_data["use_door_sensor"] = user_input["use_door_sensor"]

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

            if user_input.get("poll_interval"):
                self.data["poll_interval"] = user_input["poll_interval"]
                coordinator = self.data.get("availability_coordinator")
                if coordinator:
                    coordinator.update_interval = user_input["poll_interval"]

            if user_input.get("use_door_sensor") is not None:
                self.data["use_door_sensor"] = user_input["use_door_sensor"]

            return self.async_create_entry(title="", data=user_input)

        current_poll = self.config_entry.data.get("poll_interval", 30)
        current_door = self.config_entry.data.get("use_door_sensor", False)
        current_conn_type = self.config_entry.data.get(
            CONF_CONNECTION_TYPE, CONNECTION_TYPE_HTTP
        )

        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "connection_type", default=current_conn_type
                    ): vol.In(
                        {
                            CONNECTION_TYPE_HTTP: "HTTP (webhook)",
                            CONNECTION_TYPE_WEBSOCKET: "WebSocket (full features)",
                        }
                    ),
                    vol.Required("poll_interval", default=current_poll): vol.All(
                        vol.Coerce(int), vol.Range(min=10, max=3600)
                    ),
                    vol.Required("use_door_sensor", default=current_door): bool,
                }
            ),
            description_placeholders={
                "conn_note": "Changing connection type will reload the integration.",
            },
        )

    async def async_step_offline(self, user_input=None):
        """Show warning when controller is offline."""
        if user_input is not None:
            return await self.async_step_init()

        return self.async_show_form(
            step_id="offline",
            description_placeholders={
                "message": "Controller is offline. Settings management is limited.\n\nPlease check that the controller is powered on and connected to the network."
            },
            data_schema=vol.Schema(
                {
                    vol.Optional("refresh"): bool,
                }
            ),
        )

    async def async_step_allowed_keys(self, user_input=None):
        """Choose action for allowed keys."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "add":
                return await self.async_step_allowed_keys_add()
            elif action == "remove":
                return await self.async_step_allowed_keys_remove()

        return self.async_show_form(
            step_id="allowed_keys",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="list"): vol.In(
                        {
                            "list": "Show current allowed keys",
                            "add": "Add key",
                            "remove": "Remove key",
                        }
                    ),
                }
            ),
            description_placeholders={"keys_list": self._format_keys_list()},
        )

    async def async_step_allowed_keys_add(self, user_input=None):
        """Add a key to allowed keys."""
        errors = {}

        if user_input is not None:
            raw = (user_input.get("key_number") or "").strip()
            key_number = normalize_key_number(raw)
            if not key_number:
                errors["base"] = "key_number_required"
            else:
                name = (user_input.get("key_name") or "").strip()
                key_type = user_input.get("key_type", "normal")

                await self._add_allowed_key(key_number, name, key_type)
                self.keys = self.data.get("keys", [])
                self.hass.bus.async_fire(
                    f"{DOMAIN}_keys_updated", {"keys": self.keys}
                )
                return await self.async_step_allowed_keys()

        return self.async_show_form(
            step_id="allowed_keys_add",
            data_schema=vol.Schema(
                {
                    vol.Required("key_number"): str,
                    vol.Optional("key_name", default=""): str,
                    vol.Required("key_type", default="normal"): vol.In(
                        ["normal", "blocking", "master"]
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"keys_list": self._format_keys_list()},
        )

    async def async_step_allowed_keys_remove(self, user_input=None):
        """Remove a key from allowed keys."""
        errors = {}

        if user_input is not None:
            key_number = (user_input.get("remove_key_number") or "").strip().upper()
            if not key_number:
                errors["base"] = "key_number_required"
            else:
                key_number = normalize_key_number(key_number)
                await self._remove_allowed_key(key_number)
                self.keys = self.data.get("keys", [])
                self.hass.bus.async_fire(
                    f"{DOMAIN}_keys_updated", {"keys": self.keys}
                )
                return await self.async_step_allowed_keys()

        keys = self._normalized_keys()
        choices = {}
        for k in keys:
            choices[k["key_number"]] = (
                f"{short_key_number(k['key_number'])} — "
                f"{k.get('name') or 'unnamed'} "
                f"({k.get('type', 'normal')})"
            )

        if choices:
            schema = vol.Schema(
                {
                    vol.Required("remove_key_number"): vol.In(choices),
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required("remove_key_number"): str,
                }
            )

        return self.async_show_form(
            step_id="allowed_keys_remove",
            data_schema=schema,
            errors=errors,
            description_placeholders={"keys_list": self._format_keys_list()},
        )

    def _normalized_keys(self) -> list:
        """Return normalized keys list."""
        keys = self.data.get("keys", [])
        result = []
        for k in keys:
            if isinstance(k, str):
                try:
                    k = json.loads(k)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(k, dict) and k.get("key_number"):
                result.append(k)
        return result

    def _format_keys_list(self) -> str:
        """Format allowed keys list for display."""
        keys = self._normalized_keys()
        if not keys:
            return "No allowed keys"

        lines = []
        for i, key in enumerate(keys, 1):
            name = key.get("name") or "unnamed"
            key_num = short_key_number(key.get("key_number", ""))
            key_type = key.get("type", "normal")
            lines.append(f"{i}. {key_num} - {name} ({key_type})")

        return "\n".join(lines) if lines else "No allowed keys"

    async def _send_command_to_controller(self, command: dict):
        """Send command to controller via WebSocket server."""
        ws_server = self.data.get("ws_server")
        if not ws_server:
            _LOGGER.warning(
                "WebSocket server not available, command not sent: %s",
                command.get("operation"),
            )
            return False

        try:
            result = await ws_server.send_command(command)
            if result:
                _LOGGER.warning(
                    "Sent %s to controller", command.get("operation")
                )
            else:
                _LOGGER.warning(
                    "Failed to send %s to controller",
                    command.get("operation"),
                )
            return result
        except Exception as err:
            _LOGGER.warning(
                "Error sending %s to controller: %s",
                command.get("operation"),
                err,
            )
            return False

    async def _add_allowed_key(self, key_number: str, name: str, key_type: str):
        """Add key to allowed keys and controller."""
        if "keys" not in self.data:
            self.data["keys"] = []

        for existing in self.data["keys"]:
            if isinstance(existing, str):
                try:
                    existing = json.loads(existing)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(existing, dict) and existing.get("key_number") == key_number:
                _LOGGER.warning("Key %s already exists in allowed keys", key_number)
                return

        flags = 8 if key_type == "blocking" else 0
        key_data = {
            "key_number": key_number,
            "name": name,
            "type": key_type,
            "flags": flags,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": None,
        }
        self.data["keys"].append(key_data)

        if self.data.get("keys_store"):
            await self.data["keys_store"].async_save({"keys": self.data["keys"]})

        _LOGGER.warning("Key %s (%s) added to allowed keys", key_number, name)

        if key_type == "master":
            _LOGGER.warning(
                "Master key %s stored in Home Assistant only. Master keys "
                "cannot be added to the controller via Web-JSON. Use an "
                "iButton reader and the master key programming procedure "
                "to add it to the controller.",
                key_number,
            )
            return

        await self._send_command_to_controller(
            {
                "operation": "add_cards",
                "cards": [
                    {
                        "card": key_number,
                        "flags": flags,
                        "tz": 255,
                    }
                ],
            }
        )

    async def _remove_allowed_key(self, key_number: str):
        """Remove key from allowed keys and controller."""
        if "keys" not in self.data:
            return

        new_keys = []
        key_type = None
        for k in self.data["keys"]:
            if isinstance(k, str):
                try:
                    k = json.loads(k)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(k, dict):
                if k.get("key_number") == key_number:
                    key_type = k.get("type")
                else:
                    new_keys.append(k)
            else:
                new_keys.append(k)

        self.data["keys"] = new_keys

        if self.data.get("keys_store"):
            await self.data["keys_store"].async_save({"keys": new_keys})

        _LOGGER.warning("Key %s removed from allowed keys", key_number)

        if key_type == "master":
            _LOGGER.warning(
                "Master key %s removed from Home Assistant only. It was never "
                "sent to the controller via Web-JSON.",
                key_number,
            )
            return

        await self._send_command_to_controller(
            {
                "operation": "del_cards",
                "cards": [{"card": key_number}],
            }
        )