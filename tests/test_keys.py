"""Tests for keys.py utility module."""

import pytest
import sys
import os

# Add custom_components to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'ironlogic'))

from keys import (
    normalize_key_number,
    short_key_number,
    is_key_allowed,
    build_key_card,
    build_sync_commands,
)


class TestNormalizeKeyNumber:
    """Tests for normalize_key_number function."""

    def test_12_chars_no_prefix(self):
        """Test 12-char key without prefix."""
        assert normalize_key_number("00B5009EC1A8") == "00B5009EC1A8"

    def test_12_chars_with_0x_prefix(self):
        """Test 12-char key with 0x prefix."""
        assert normalize_key_number("0x00B5009EC1A8") == "00B5009EC1A8"

    def test_12_chars_with_0X_prefix(self):
        """Test 12-char key with 0X prefix."""
        assert normalize_key_number("0X00B5009EC1A8") == "00B5009EC1A8"

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
        """Test short key (last 6 chars) match returns 1."""
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("9EC1A8", keys) == 1

    def test_case_insensitive_match(self):
        """Test case insensitive match."""
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("9ec1a8", keys) == 1

    def test_blocking_key_returns_0(self):
        """Test blocking key returns 0 (denied)."""
        keys = [{"key_number": "00B5009EC1A8", "type": "blocking"}]
        assert is_key_allowed("00B5009EC1A8", keys) == 0

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

    def test_key_with_0x_prefix(self):
        """Test key with 0x prefix."""
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("0x00B5009EC1A8", keys) == 1


class TestBuildKeyCard:
    """Tests for build_key_card function."""

    def test_normal_key(self):
        """Test building normal key card."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Test Key",
            "type": "normal",
            "flags": 0,
        }
        card = build_key_card(key_data)
        assert card["key"] == "00B5009EC1A8"
        assert card["flags"] == 0

    def test_blocking_key(self):
        """Test building blocking key card."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Blocked Key",
            "type": "blocking",
            "flags": 8,
        }
        card = build_key_card(key_data)
        assert card["key"] == "00B5009EC1A8"
        assert card["flags"] == 8

    def test_master_key_excluded(self):
        """Test master key is excluded (returns None)."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Master Key",
            "type": "master",
            "flags": 0,
        }
        card = build_key_card(key_data)
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
        assert commands[0]["operation"] == "add_keys"
        assert len(commands[0]["keys"]) == 1

    def test_multiple_keys_batched(self):
        """Test multiple keys batched by SYNC_BATCH_SIZE."""
        keys = [
            {"key_number": f"00000000000{i}", "type": "normal", "flags": 0}
            for i in range(55)
        ]
        commands = build_sync_commands(keys, 1, batch_size=50)
        # Should be 2 commands: 50 + 5
        assert len(commands) == 2
        assert len(commands[0]["keys"]) == 50
        assert len(commands[1]["keys"]) == 5

    def test_master_keys_excluded_from_sync(self):
        """Test master keys are excluded from sync commands."""
        keys = [
            {"key_number": "00B5009EC1A8", "type": "normal", "flags": 0},
            {"key_number": "00B5009EC1A9", "type": "master", "flags": 0},
        ]
        commands = build_sync_commands(keys, 1)
        assert len(commands) == 1
        assert len(commands[0]["keys"]) == 1
        assert commands[0]["keys"][0]["key"] == "00B5009EC1A8"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])