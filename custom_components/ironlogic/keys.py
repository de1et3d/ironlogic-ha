"""Key utilities for IronLogic IP Controller."""

import json
from typing import Any


def normalize_key_number(value: str) -> str:
    """Normalize user-entered key number to 12 hex characters."""
    if not value:
        return ""
    value = value.strip().upper().replace(" ", "")
    if not value:
        return ""
    if len(value) <= 12:
        return value.zfill(12)
    return value[-12:]


def short_key_number(value: str) -> str:
    """Return short display form (last 6 characters)."""
    if not value:
        return ""
    return value[-6:]


def is_key_allowed(key_id: str, keys: list[dict[str, Any]]) -> int:
    """Check if key is in allowed list."""
    if not key_id or not keys:
        return 0
    
    normalized_key_id = normalize_key_number(key_id)
    short_key_id = short_key_number(normalized_key_id).upper()
    
    for key in keys:
        if isinstance(key, str):
            try:
                key = json.loads(key)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(key, dict):
            stored_key = key.get("key_number", "")
            stored_type = key.get("type", "normal")
            
            if stored_key == normalized_key_id:
                return 0 if stored_type == "blocking" else 1
            if stored_key and short_key_number(stored_key).upper() == short_key_id:
                return 0 if stored_type == "blocking" else 1
    return 0


def build_key_card(key: dict[str, Any]) -> dict[str, Any]:
    """Build card dict from key data for controller commands."""
    if key.get("type") == "master":
        return None
    
    flags = key.get("flags", 0)
    if key.get("type") == "blocking" and flags == 0:
        flags = 8
    return {
        "key": key["key_number"],
        "flags": flags,
        "tz": 255,
    }


def build_sync_commands(keys: list[dict[str, Any]], start_id: int, batch_size: int = 50) -> list[dict[str, Any]]:
    """Build sync commands for controller."""
    commands = []
    current_id = start_id
    batch = []
    
    for key in keys:
        if isinstance(key, str):
            try:
                key = json.loads(key)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(key, dict):
            continue
            
        if key.get("type") == "master":
            continue
            
        card = build_key_card(key)
        if card:
            batch.append(card)
            
        if len(batch) >= batch_size:
            current_id += 1
            commands.append({
                "id": current_id,
                "operation": "add_keys",
                "keys": batch,
            })
            batch = []
    
    if batch:
        current_id += 1
        commands.append({
            "id": current_id,
            "operation": "add_keys",
            "keys": batch,
        })
    
    return commands