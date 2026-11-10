"""Key utilities for IronLogic IP Controller."""

import json
from typing import Any


def normalize_key_number(value: str) -> str:
    """Normalize user-entered key number to 12 hex characters.

    Short input (6 chars or less) is padded with leading zeros to 12 chars
    (Wiegand short form). Longer input (7-12 chars) is padded with leading
    zeros to 12 chars. Input longer than 12 chars is rejected (returns "").
    """
    if not value:
        return ""
    value = value.strip().upper().replace(" ", "")
    if not value:
        return ""
    if len(value) <= 12:
        return value.zfill(12)
    return ""


def short_key_number(value: str) -> str:
    """Return short display form (last 6 characters)."""
    if not value:
        return ""
    return value[-6:]


def is_key_allowed(key_id: str, keys: list[dict[str, Any]]) -> int:
    """Check if key is in allowed list.

    Both normal and blocking keys are allowed. The "Blocking" door mode is
    a controller-side state, not an allowed-keys property.
    """
    if not key_id or not keys:
        return 0

    normalized_key_id = normalize_key_number(key_id)
    if not normalized_key_id:
        return 0

    for key in keys:
        if isinstance(key, str):
            try:
                key = json.loads(key)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(key, dict):
            stored_key = key.get("key_number", "")
            if stored_key == normalized_key_id:
                return 1
    return 0


def build_key_payload(key: dict[str, Any]) -> dict[str, Any] | None:
    """Build controller payload for a key.

    Note: the Web-JSON protocol uses "card"/"cards" field names and
    "add_cards"/"del_cards"/"clear_cards" operation names. This is the
    only place where "card" terminology is used.
    """
    if key.get("type") == "master":
        return None

    flags = key.get("flags", 0)
    if key.get("type") == "blocking" and flags == 0:
        flags = 8
    return {
        "card": key["key_number"],
        "flags": flags,
        "tz": 255,
    }


def build_sync_commands(
    keys: list[dict[str, Any]], start_id: int, batch_size: int = 50
) -> list[dict[str, Any]]:
    """Build commands to sync allowed keys to controller."""
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

        payload = build_key_payload(key)
        if payload:
            batch.append(payload)

        if len(batch) >= batch_size:
            current_id += 1
            commands.append({
                "id": current_id,
                "operation": "add_cards",
                "cards": batch,
            })
            batch = []

    if batch:
        current_id += 1
        commands.append({
            "id": current_id,
            "operation": "add_cards",
            "cards": batch,
        })

    return commands