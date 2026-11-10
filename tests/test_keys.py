"""Tests for keys.py utility module."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'ironlogic'))

from keys import (
    normalize_key_number,
    short_key_number,
    is_key_allowed,
    build_key_payload,
    build_sync_commands,
)


class TestNormalizeKeyNumber:
    """Tests for normalize_key_number function."""

    def test_12_chars_no_prefix(self):
        """Test 12-char key without prefix."""
        assert normalize_key_number("00B5009EC1A8") == "00B5009EC1A8"

    def test_14_chars_with_0x_prefix_rejected(self):
        """Test 14-char key with 0x prefix is rejected (>12 chars)."""
        assert normalize_key_number("0x00B5009EC1A8") == ""

    def test_14_chars_with_0X_prefix_rejected(self):
        """Test 14-char key with 0X prefix is rejected (>12 chars)."""
        assert normalize_key_number("0X00B5009EC1A8") == ""

    def test_10_chars_padded_with_zeros(self):
        """Test 10-char key padded with leading zeros."""
        assert normalize_key_number("B5009EC1A8") == "00B5009EC1A8"

    def test_8_chars_padded_with_zeros(self):
        """Test 8-char key padded with leading zeros."""
        assert normalize_key_number("9EC1A8") == "0000009EC1A8"

    def test_lowercase_converted_to_uppercase(self):
        """Test lowercase is converted to uppercase."""
        assert normalize_key_number("00b5009ec1a8") == "00B5009EC1A8"

    def test_empty_string_returns_empty(self):
        """Test empty string returns empty."""
        assert normalize_key_number("") == ""

    def test_none_returns_empty(self):
        """Test None returns empty string."""
        assert normalize_key_number(None) == ""

    def test_whitespace_stripped(self):
        """Test whitespace is stripped."""
        assert normalize_key_number(" 00B5009EC1A8 ") == "00B5009EC1A8"


class TestShortKeyNumber:
    """Tests for short_key_number function."""

    def test_returns_last_6_chars(self):
        """Test returns last 6 characters."""
        assert short_key_number("00B5009EC1A8") == "9EC1A8"

    def test_returns_full_string_if_shorter_than_6(self):
        """Test returns full string if shorter than 6 chars."""
        assert short_key_number("ABC") == "ABC"

    def test_returns_empty_for_empty(self):
        """Test returns empty for empty string."""
        assert short_key_number("") == ""


class TestIsKeyAllowed:
    """Tests for is_key_allowed function."""

    def test_exact_match_returns_1(self):
        """Test exact match returns 1 (granted)."""
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("00B5009EC1A8", keys) == 1

    def test_short_key_match_returns_1(self):
        """Test short key (last 6 chars) padded to 12 chars returns 1."""
        # Short key "9EC1A8" normalizes to "0000009EC1A8"
        keys = [{"key_number": "0000009EC1A8", "type": "normal"}]
        assert is_key_allowed("9EC1A8", keys) == 1

    def test_case_insensitive_match(self):
        """Test case insensitive match."""
        keys = [{"key_number": "0000009EC1A8", "type": "normal"}]
        assert is_key_allowed("9ec1a8", keys) == 1

    def test_blocking_key_returns_1(self):
        """Test blocking key returns 1 (both normal and blocking are allowed)."""
        keys = [{"key_number": "00B5009EC1A8", "type": "blocking"}]
        assert is_key_allowed("00B5009EC1A8", keys) == 1

    def test_unknown_key_returns_0(self):
        """Test unknown key returns 0."""
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("000000000000", keys) == 0

    def test_empty_keys_returns_0(self):
        """Test empty keys list returns 0."""
        assert is_key_allowed("00B5009EC1A8", []) == 0

    def test_none_keys_returns_0(self):
        """Test None keys list returns 0."""
        assert is_key_allowed("00B5009EC1A8", None) == 0


class TestBuildKeyPayload:
    """Tests for build_key_payload function."""

    def test_normal_key(self):
        """Test building normal key payload."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Test Key",
            "type": "normal",
            "flags": 0,
        }
        card = build_key_payload(key_data)
        assert card is not None
        assert card["card"] == "00B5009EC1A8"
        assert card["flags"] == 0
        assert card["tz"] == 255

    def test_blocking_key_with_zero_flags(self):
        """Test blocking key with zero flags gets default flags=8."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Blocked Key",
            "type": "blocking",
            "flags": 0,
        }
        card = build_key_payload(key_data)
        assert card is not None
        assert card["card"] == "00B5009EC1A8"
        assert card["flags"] == 8

    def test_blocking_key_with_custom_flags(self):
        """Test blocking key with custom flags keeps those flags."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Blocked Key",
            "type": "blocking",
            "flags": 4,
        }
        card = build_key_payload(key_data)
        assert card is not None
        assert card["flags"] == 4

    def test_master_key_excluded(self):
        """Test master key is excluded (returns None)."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Master Key",
            "type": "master",
            "flags": 0,
        }
        card = build_key_payload(key_data)
        assert card is None


class TestBuildSyncCommands:
    """Tests for build_sync_commands function."""

    def test_empty_keys_returns_empty_list(self):
        """Test empty keys returns empty list."""
        commands = build_sync_commands([], 1)
        assert commands == []

    def test_single_key_returns_one_command(self):
        """Test single key returns one command."""
        keys = [{"key_number": "00B5009EC1A8", "type": "normal", "flags": 0}]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert commands[0]["operation"] == "add_cards"
        assert len(commands[0]["cards"]) == 1
        assert commands[0]["cards"][0]["card"] == "00B5009EC1A8"

    def test_multiple_keys_batched(self):
        """Test multiple keys batched by batch_size."""
        keys = [
            {"key_number": f"0000000000{i:02d}", "type": "normal", "flags": 0}
            for i in range(55)
        ]
        commands = build_sync_commands(keys, 1, batch_size=50)
        assert len(commands) == 2
        assert len(commands[0]["cards"]) == 50
        assert len(commands[1]["cards"]) == 5

    def test_master_keys_excluded_from_sync(self):
        """Test master keys are excluded from sync commands."""
        keys = [
            {"key_number": "00B5009EC1A8", "type": "normal", "flags": 0},
            {"key_number": "00B5009EC1A9", "type": "master", "flags": 0},
        ]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert len(commands[0]["cards"]) == 1
        assert commands[0]["cards"][0]["card"] == "00B5009EC1A8"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])