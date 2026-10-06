"""Options flow for IronLogic IP Controller."""

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
        """Manage allowed keys whitelist."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "add":
                key_number = (user_input.get("key_number") or "").strip().upper()
                if not key_number:
                    return self.async_show_form(
                        step_id="allowed_keys",
                        data_schema=self._keys_schema(),
                        errors={"base": "key_number_required"},
                        description_placeholders={
                            "keys_list": self._format_keys_list()
                        },
                    )

                name = (user_input.get("key_name") or "").strip()
                key_type = user_input.get("key_type", "normal")

                await self._add_allowed_key(key_number, name, key_type)
                self.keys = self.data.get("keys", [])
                self.hass.bus.async_fire(
                    f"{DOMAIN}_keys_updated", {"keys": self.keys}
                )
                return self.async_show_form(
                    step_id="allowed_keys",
                    data_schema=self._keys_schema(),
                    description_placeholders={
                        "keys_list": self._format_keys_list()
                    },
                )

            elif action == "remove":
                key_number = (user_input.get("remove_key_number") or "").strip().upper()
                if key_number:
                    await self._remove_allowed_key(key_number)
                    self.keys = self.data.get("keys", [])
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_keys_updated", {"keys": self.keys}
                    )
                return self.async_show_form(
                    step_id="allowed_keys",
                    data_schema=self._keys_schema(),
                    description_placeholders={
                        "keys_list": self._format_keys_list()
                    },
                )

            elif action == "refresh":
                self.keys = self.data.get("keys", [])
                return self.async_show_form(
                    step_id="allowed_keys",
                    data_schema=self._keys_schema(),
                    description_placeholders={
                        "keys_list": self._format_keys_list()
                    },
                )

        return self.async_show_form(
            step_id="allowed_keys",
            data_schema=self._keys_schema(),
            description_placeholders={"keys_list": self._format_keys_list()},
        )

    def _keys_schema(self):
        """Return schema for keys form."""
        return vol.Schema(
            {
                vol.Optional("action", default="refresh"): vol.In(
                    {
                        "refresh": "Refresh list",
                        "add": "Add key",
                        "remove": "Remove key",
                    }
                ),
                vol.Optional("key_number"): str,
                vol.Optional("key_name"): str,
                vol.Optional("key_type", default="normal"): vol.In(
                    ["normal", "blocking"]
                ),
                vol.Optional("remove_key_number"): str,
            }
        )

    def _format_keys_list(self) -> str:
        """Format keys list for display."""
        keys = self.data.get("keys", [])
        if not keys:
            return "No keys in whitelist"

        lines = []
        for i, key in enumerate(keys, 1):
            if isinstance(key, str):
                import json
                try:
                    key = json.loads(key)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(key, dict):
                name = key.get("name") or "unnamed"
                key_num = key.get("key_number", "")
                key_type = key.get("type", "normal")
                lines.append(f"{i}. {key_num} - {name} ({key_type})")

        return "\n".join(lines) if lines else "No keys in whitelist"

    async def _add_allowed_key(self, key_number: str, name: str, key_type: str):
        """Add key to whitelist."""
        if "keys" not in self.data:
            self.data["keys"] = []

        for existing in self.data["keys"]:
            if isinstance(existing, str):
                import json
                try:
                    existing = json.loads(existing)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(existing, dict) and existing.get("key_number") == key_number:
                _LOGGER.warning("Key %s already exists in whitelist", key_number)
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

        _LOGGER.info("Key %s (%s) added to whitelist", key_number, name)

    async def _remove_allowed_key(self, key_number: str):
        """Remove key from whitelist."""
        if "keys" not in self.data:
            return

        new_keys = []
        for k in self.data["keys"]:
            if isinstance(k, str):
                import json
                try:
                    k = json.loads(k)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(k, dict) and k.get("key_number") != key_number:
                new_keys.append(k)

        self.data["keys"] = new_keys

        if self.data.get("keys_store"):
            await self.data["keys_store"].async_save({"keys": new_keys})

        _LOGGER.info("Key %s removed from whitelist", key_number)