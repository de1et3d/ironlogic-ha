"""Tests for build_sync_commands function."""

import pytest

from keys import build_sync_commands


class TestBuildSyncCommands:
    """Tests for build_sync_commands function."""

    def test_empty_keys_returns_empty_list(self):
        commands = build_sync_commands([], 1)
        assert commands == []

    def test_none_keys_returns_empty_list(self):
        commands = build_sync_commands(None, 1)
        assert commands == []

    def test_single_key_returns_one_command(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal", "flags": 0}]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert commands[0]["operation"] == "add_cards"
        assert len(commands[0]["cards"]) == 1
        assert commands[0]["cards"][0]["card"] == "00B5009EC1A8"

    def test_multiple_keys_batched(self):
        keys = [
            {"key_number": f"0000000000{i:02d}", "type": "normal", "flags": 0}
            for i in range(55)
        ]
        commands = build_sync_commands(keys, 1, batch_size=50)
        assert len(commands) == 2
        assert len(commands[0]["cards"]) == 50
        assert len(commands[1]["cards"]) == 5

    def test_master_keys_excluded_from_sync(self):
        keys = [
            {"key_number": "00B5009EC1A8", "type": "normal", "flags": 0},
            {"key_number": "00B5009EC1A9", "type": "master", "flags": 0},
        ]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert len(commands[0]["cards"]) == 1
        assert commands[0]["cards"][0]["card"] == "00B5009EC1A8"

    def test_start_id_respected(self):
        keys = [
            {"key_number": f"0000000000{i:02d}", "type": "normal", "flags": 0}
            for i in range(3)
        ]
        commands = build_sync_commands(keys, 100, batch_size=2)
        assert commands[0]["id"] == 101
        assert commands[1]["id"] == 102

    def test_broken_json_string_skipped(self):
        keys = [
            "not a json",
            {"key_number": "00B5009EC1A8", "type": "normal", "flags": 0},
        ]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert len(commands[0]["cards"]) == 1

    def test_all_master_returns_empty(self):
        keys = [
            {"key_number": "00B5009EC1A8", "type": "master", "flags": 0},
            {"key_number": "00B5009EC1A9", "type": "master", "flags": 0},
        ]
        commands = build_sync_commands(keys, 1)
        assert commands == []

    def test_blocking_flags_in_payload(self):
        keys = [
            {"key_number": "00B5009EC1A8", "type": "blocking", "flags": 0},
        ]
        commands = build_sync_commands(keys, 1)
        assert commands[0]["cards"][0]["flags"] == 8


class TestEmptyKeysProtection:
    """Tests for empty-keys protection (controller keeps its own base)."""

    def test_empty_keys_list_does_not_generate_clear(self):
        """Empty HA keys must NOT trigger clear_cards — controller keeps base."""
        commands = build_sync_commands([], 1)
        assert commands == []

    def test_none_keys_does_not_generate_clear(self):
        commands = build_sync_commands(None, 1)
        assert commands == []

    def test_ha_with_keys_generates_add_commands(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal", "flags": 0}]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert commands[0]["operation"] == "add_cards"