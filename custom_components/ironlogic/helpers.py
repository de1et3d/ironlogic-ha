"""Shared helpers for IronLogic integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_update_entry_data(
    hass: HomeAssistant, entry_id: str, **kwargs: Any
) -> None:
    """Update entry data without full reload (for controls)."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry:
        new_data = {**entry.data, **kwargs}
        hass.config_entries.async_update_entry(entry, data=new_data)
        data = hass.data.get(DOMAIN, {}).get(entry_id)
        if data:
            for key, value in kwargs.items():
                data[key] = value
