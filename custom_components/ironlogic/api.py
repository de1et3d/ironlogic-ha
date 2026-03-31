"""API wrapper for IronLogic IP Controller."""

import asyncio
import logging
import json

import aiohttp

_LOGGER = logging.getLogger(__name__)


class IronLogicAPI:
    """API wrapper for IronLogic IP Controller."""

    def __init__(self, host: str, username: str, auth_key: str) -> None:
        """Initialize API."""
        self.host = host
        self.username = username
        self.auth_key = auth_key
        self.base_url = f"http://{self.host}"

    async def check_availability(self) -> bool:
        """Check if controller is reachable."""
        url = f"{self.base_url}/"
        auth = aiohttp.BasicAuth(self.username, self.auth_key)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, timeout=5) as resp:
                    return resp.status < 500
        except asyncio.TimeoutError:
            _LOGGER.debug("Controller %s timed out", self.host)
            return False
        except aiohttp.ClientError as err:
            _LOGGER.debug("Controller %s connection error: %s", self.host, err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected error checking controller %s: %s", self.host, err)
            return False

    async def open_door(self) -> bool:
        """Open door via HTTP API."""
        url = f"{self.base_url}/door"
        auth = aiohttp.BasicAuth(self.username, self.auth_key)
        payload = {"dir": 0}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    auth=auth,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    success = resp.status == 200
                    if not success:
                        _LOGGER.error("Open door failed with code %d", resp.status)
                    return success
        except asyncio.TimeoutError as err:
            _LOGGER.error("Open door request timeout: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Open door request failed: %s", err)
            return False

    async def reboot(self) -> bool:
        """Reboot controller via HTTP API."""
        url = f"{self.base_url}/reset"
        auth = aiohttp.BasicAuth(self.username, self.auth_key)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, timeout=10) as resp:
                    if resp.status == 200:
                        _LOGGER.info("Controller reboot command sent")
                        return True
                    else:
                        _LOGGER.error("Reboot failed with code %d", resp.status)
                        return False
        except asyncio.TimeoutError as err:
            _LOGGER.error("Reboot request timeout: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Reboot request failed: %s", err)
            return False

    async def get_settings(self) -> dict | None:
        """Get current controller settings."""
        url = f"{self.base_url}/workmode"
        auth = aiohttp.BasicAuth(self.username, self.auth_key)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        _LOGGER.debug("Raw settings response: %s", text)
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError as err:
                            _LOGGER.error("Failed to parse JSON: %s", err)
                            return None
                    _LOGGER.error("Get settings failed with code %d", resp.status)
                    return None
        except asyncio.TimeoutError as err:
            _LOGGER.error("Get settings timeout: %s", err)
            return None
        except Exception as err:
            _LOGGER.error("Get settings failed: %s", err)
            return None

    async def set_webhook_url(self, webhook_url: str, period: int = 10) -> bool:
        """Set webhook URL in controller."""
        # Get current settings
        settings = await self.get_settings()
        if not settings:
            _LOGGER.error("Failed to get current settings")
            return False

        # Update webjson section
        if "webjson" not in settings:
            settings["webjson"] = {}
        
        settings["webjson"]["server"] = webhook_url
        settings["webjson"]["period"] = period
        settings["webjson"]["protocol"] = 0  # HTTP (0 = HTTP, 1 = HTTPS)
        settings["webjson"]["login"] = ""
        settings["webjson"]["password"] = ""
        
        # Ensure mode is Web-JSON (4)
        settings["mode"] = 4

        # Send back
        url = f"{self.base_url}/save_workmode"
        auth = aiohttp.BasicAuth(self.username, self.auth_key)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    auth=auth,
                    json=settings,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        _LOGGER.info("Webhook URL set successfully")
                        return True
                    else:
                        _LOGGER.error("Set webhook failed with code %d", resp.status)
                        return False
        except asyncio.TimeoutError as err:
            _LOGGER.error("Set webhook timeout: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Set webhook failed: %s", err)
            return False