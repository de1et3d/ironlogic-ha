"""API wrapper for IronLogic IP Controller."""

import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlparse

import aiohttp

from .const import CONNECTION_TYPE_WEBSOCKET

_LOGGER = logging.getLogger(__name__)

WEBHOOK_URL_PATTERN = re.compile(
    r"^https?://"  # http:// or https://
    r"[^\s/$.?#].[^\s]*$"  # domain and optional path
)

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 10.0  # seconds
DEFAULT_EXPONENTIAL_BASE = 2.0


class IronLogicAPI:
    """API wrapper for IronLogic IP Controller."""

    def __init__(self, host: str, username: str, auth_key: str) -> None:
        """Initialize API."""
        self.host = host
        self.username = username
        self.auth_key = auth_key
        self.base_url = f"http://{self.host}"

    async def _retry_with_backoff(
        self,
        func: Callable[..., Any],
        *args: Any,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
        **kwargs: Any,
    ) -> Any:
        """Execute function with exponential backoff retry logic.

        Args:
            func: Async function to execute
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Exponential base for backoff
            *args, **kwargs: Arguments to pass to func

        Returns:
            Result of func if successful

        Raises:
            Last exception if all retries exhausted
        """
        last_exception: BaseException | None = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except (TimeoutError, aiohttp.ClientError) as err:
                last_exception = err
                if attempt < max_retries:
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    _LOGGER.debug(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                        attempt + 1,
                        max_retries + 1,
                        func.__name__,
                        err,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    _LOGGER.exception(
                        "All %d attempts failed for %s: %s",
                        max_retries + 1,
                        func.__name__,
                        err,
                    )
            except Exception as err:
                _LOGGER.exception("Non-retryable error in %s: %s", func.__name__, err)
                raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry failed with no exception")

    async def check_availability(self) -> bool:
        """Check if controller is reachable."""
        async def _check() -> bool:
            url = f"{self.base_url}/"
            auth = aiohttp.BasicAuth(self.username, self.auth_key)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, timeout=5) as resp:
                    return resp.status < 500

        try:
            return await self._retry_with_backoff(_check)
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Controller %s timed out after retries: %s", self.host, err)
            return False
        except Exception as err:
            _LOGGER.exception("Unexpected error checking controller %s: %s", self.host, err)
            return False

    async def open_door(self) -> bool:
        """Open door via HTTP API."""
        async def _open() -> bool:
            url = f"{self.base_url}/door"
            auth = aiohttp.BasicAuth(self.username, self.auth_key)
            payload = {"dir": 0}

            async with aiohttp.ClientSession() as session, session.post(
                url,
                auth=auth,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                success = resp.status == 200
                if not success:
                    _LOGGER.error("Open door failed with code %d", resp.status)
                return success

        try:
            return await self._retry_with_backoff(_open)
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.exception("Open door request timeout after retries: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Open door request failed: %s", err)
            return False

    async def reboot(self) -> bool:
        """Reboot controller via HTTP API."""
        async def _reboot() -> bool:
            url = f"{self.base_url}/reset"
            auth = aiohttp.BasicAuth(self.username, self.auth_key)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, timeout=10) as resp:
                    if resp.status == 200:
                        _LOGGER.info("Controller reboot command sent")
                        return True
                    else:
                        _LOGGER.error("Reboot failed with code %d", resp.status)
                        return False

        try:
            return await self._retry_with_backoff(_reboot)
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.exception("Reboot request timeout after retries: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Reboot request failed: %s", err)
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
                            _LOGGER.exception("Failed to parse JSON: %s", err)
                            return None
                    _LOGGER.error("Get settings failed with code %d", resp.status)
                    return None
        except TimeoutError as err:
            _LOGGER.exception("Get settings timeout: %s", err)
            return None
        except Exception as err:
            _LOGGER.exception("Get settings failed: %s", err)
            return None

    async def set_webhook_url(self, webhook_url: str, period: int = 10, connection_type: str | None = None) -> bool:
        """Set webhook URL in controller."""
        if not self._validate_webhook_url(webhook_url):
            _LOGGER.error("Invalid webhook URL format: %s", webhook_url)
            return False

        settings = await self.get_settings()
        if not settings:
            _LOGGER.error("Failed to get current settings")
            return False

        if "webjson" not in settings:
            settings["webjson"] = {}

        if connection_type == CONNECTION_TYPE_WEBSOCKET:
            ws_url = webhook_url.replace("http://", "ws://").replace("https://", "wss://")
            settings["webjson"]["server"] = ws_url
            settings["webjson"]["protocol"] = True
            _LOGGER.info("Using WebSocket URL: %s", ws_url)
        else:
            settings["webjson"]["server"] = webhook_url
            settings["webjson"]["protocol"] = False

        settings["webjson"]["period"] = period
        settings["webjson"]["login"] = ""
        settings["webjson"]["password"] = ""

        settings["mode"] = 4

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
                        _LOGGER.info("Webhook URL set successfully (protocol=%s)",
                                    "WebSocket" if connection_type == CONNECTION_TYPE_WEBSOCKET else "HTTP")
                        return True
                    else:
                        _LOGGER.error("Set webhook failed with code %d", resp.status)
                        return False
        except TimeoutError as err:
            _LOGGER.exception("Set webhook timeout: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Set webhook failed: %s", err)
            return False

    def _validate_webhook_url(self, url: str) -> bool:
        """Validate webhook URL format."""
        if not url:
            return False

        if not WEBHOOK_URL_PATTERN.match(url):
            return False

        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                return False
            if not parsed.netloc:
                return False
            return True
        except Exception:
            return False
