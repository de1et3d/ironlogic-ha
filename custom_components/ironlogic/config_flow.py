"""Config flow for IronLogic IP Controller integration."""

import asyncio
import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AUTH_KEY,
    CONF_CONNECTION_TYPE,
    CONNECTION_TYPE_HTTP,
    CONNECTION_TYPE_WEBSOCKET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_AUTH_KEY): str,
    }
)


class IronLogicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IronLogic."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._scanned_hosts = []
        self._manual_host = None
        self._manual_username = None
        self._manual_auth_key = None
        self._selected_host = None
        self._selected_username = None
        self._selected_auth_key = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow."""
        from .options_flow import IronLogicOptionsFlowHandler
        return IronLogicOptionsFlowHandler()

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step: choose manual or scan."""
        if user_input is not None:
            if user_input.get("setup_method") == "scan":
                return await self.async_step_scan()
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("setup_method", default="manual"): vol.In(
                        {
                            "manual": "Configure manually",
                            "scan": "Scan network for controllers",
                        }
                    ),
                }
            ),
        )

    async def async_step_manual(self, user_input: dict | None = None) -> FlowResult:
        """Manual configuration step - enter IP."""
        errors = {}

        if user_input is not None:
            try:
                await self._test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_AUTH_KEY],
                )

                self._manual_host = user_input[CONF_HOST]
                self._manual_username = user_input[CONF_USERNAME]
                self._manual_auth_key = user_input[CONF_AUTH_KEY]
                
                return await self.async_step_connection_type()
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "username_hint": "For Z-5R (Wi-Fi): z5rwifi\nFor Z-5R Web: z5rweb\nFor Matrix-II (Wi-Fi): matrix",
                "auth_key_hint": "8-character key from the controller label",
            },
        )

    async def async_step_scan(self, user_input: dict | None = None) -> FlowResult:
        """Scan local network for controllers."""
        if user_input is None:
            return self.async_show_form(
                step_id="scan",
                data_schema=vol.Schema({}),
            )

        await self._scan_network()

        if not self._scanned_hosts:
            return self.async_show_form(
                step_id="scan_failed",
                data_schema=vol.Schema({}),
            )

        return await self.async_step_select_host()

    async def async_step_scan_failed(self, user_input: dict | None = None) -> FlowResult:
        """Handle scan failed."""
        if user_input is not None:
            return await self.async_step_manual()
        return self.async_show_form(
            step_id="scan_failed",
            data_schema=vol.Schema(
                {
                    vol.Optional("retry"): bool,
                }
            ),
            errors={"base": "no_devices_found"},
        )

    async def async_step_select_host(self, user_input: dict | None = None) -> FlowResult:
        """Select host from scanned list."""
        if user_input is not None:
            self._selected_host = user_input["host"]
            self._selected_username = user_input[CONF_USERNAME]
            self._selected_auth_key = user_input[CONF_AUTH_KEY]
            
            try:
                await self._test_connection(
                    self._selected_host,
                    self._selected_username,
                    self._selected_auth_key,
                )
                return await self.async_step_connection_type()
            except CannotConnect:
                return self.async_show_form(
                    step_id="select_host",
                    data_schema=vol.Schema(
                        {
                            vol.Required("host"): vol.In(self._scanned_hosts),
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_AUTH_KEY): str,
                        }
                    ),
                    errors={"base": "cannot_connect"},
                )
            except InvalidAuth:
                return self.async_show_form(
                    step_id="select_host",
                    data_schema=vol.Schema(
                        {
                            vol.Required("host"): vol.In(self._scanned_hosts),
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_AUTH_KEY): str,
                        }
                    ),
                    errors={"base": "invalid_auth"},
                )

        return self.async_show_form(
            step_id="select_host",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): vol.In(self._scanned_hosts),
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_AUTH_KEY): str,
                }
            ),
        )

    async def async_step_connection_type(self, user_input: dict | None = None) -> FlowResult:
        """Choose Web-JSON protocol type."""
        if user_input is not None:
            connection_type = user_input.get("connection_type")
            
            if self._selected_host is not None:
                data = {
                    CONF_HOST: self._selected_host,
                    CONF_USERNAME: self._selected_username,
                    CONF_AUTH_KEY: self._selected_auth_key,
                    CONF_CONNECTION_TYPE: connection_type,
                }
            else:
                data = {
                    CONF_HOST: self._manual_host,
                    CONF_USERNAME: self._manual_username,
                    CONF_AUTH_KEY: self._manual_auth_key,
                    CONF_CONNECTION_TYPE: connection_type,
                }
            
            await self.async_set_unique_id(f"ironlogic_{data[CONF_HOST]}")
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"IronLogic ({data[CONF_HOST]})",
                data=data,
            )

        return self.async_show_form(
            step_id="connection_type",
            data_schema=vol.Schema(
                {
                    vol.Required("connection_type", default=CONNECTION_TYPE_HTTP): vol.In(
                        {
                            CONNECTION_TYPE_HTTP: "HTTP (webhook)",
                            CONNECTION_TYPE_WEBSOCKET: "WebSocket (full features)",
                        }
                    ),
                }
            ),
            description_placeholders={
                "note": "Select the protocol mode configured in your controller."
            },
        )

    async def _scan_network(self) -> None:
        """Scan local network for IronLogic controllers."""
        self._scanned_hosts = []
        
        ips_to_scan = await self._get_local_ips()
        
        if not ips_to_scan:
            _LOGGER.error("Could not determine IPs to scan")
            return

        _LOGGER.info("Scanning %d IP addresses", len(ips_to_scan))
        
        tasks = []
        session = async_get_clientsession(self.hass)
        
        for ip in ips_to_scan:
            tasks.append(self._check_host(session, ip))
        
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=30)
            self._scanned_hosts = [ip for ip, found in zip(ips_to_scan, results) if found]
            _LOGGER.info("Found %d IronLogic controllers: %s", len(self._scanned_hosts), self._scanned_hosts)
        except asyncio.TimeoutError:
            _LOGGER.warning("Network scan timeout")

    async def _get_local_ips(self) -> list[str]:
        """Get list of IPs to scan on local network."""
        ips = []
        try:
            ha_ip = self.hass.config.api.local_ip
            
            if not ha_ip:
                raise ValueError("No local IP found")
            
            _LOGGER.debug("HA local IP: %s", ha_ip)
            
            parts = ha_ip.split(".")
            if len(parts) != 4:
                raise ValueError(f"Invalid IP: {ha_ip}")
            
            base = f"{parts[0]}.{parts[1]}.{parts[2]}"
            
            for i in range(1, 255):
                ips.append(f"{base}.{i}")
            
            _LOGGER.debug("Scanning /24 network: %s.0/24", base)
            
        except Exception as e:
            _LOGGER.error("Could not determine local network: %s", e)
            return []
            
        return ips[:250]

    async def _check_host(self, session: aiohttp.ClientSession, ip: str) -> bool:
        """Check if host is an IronLogic controller."""
        url = f"http://{ip}/"
        
        try:
            async with session.get(url, timeout=2) as resp:
                _LOGGER.debug("Checking %s - Status: %d, Headers: %s", ip, resp.status, dict(resp.headers))
                
                auth_header = resp.headers.get("WWW-Authenticate", "")
                if auth_header and "Z-5R" in auth_header:
                    _LOGGER.info("Found IronLogic controller at %s", ip)
                    return True
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout checking %s", ip)
        except aiohttp.ClientError as e:
            _LOGGER.debug("Client error checking %s: %s", ip, e)
        except Exception as e:
            _LOGGER.debug("Unexpected error checking %s: %s", ip, e)
        
        return False

    async def _test_connection(self, host: str, username: str, auth_key: str) -> bool:
        """Test connection to controller."""
        from aiohttp import BasicAuth, ClientError, ClientResponseError

        session = async_get_clientsession(self.hass)
        auth = BasicAuth(username, auth_key)
        url = f"http://{host}/"

        try:
            async with session.get(url, auth=auth, timeout=10) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                return True
        except ClientResponseError as err:
            _LOGGER.debug("HTTP error connecting to %s: %s", host, err)
            raise CannotConnect from err
        except ClientError as err:
            _LOGGER.debug("Connection error to %s: %s", host, err)
            raise CannotConnect from err
        except Exception as err:
            _LOGGER.debug("Unexpected error connecting to %s: %s", host, err)
            raise CannotConnect from err


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""