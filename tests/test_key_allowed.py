"""Tests for is_key_allowed function."""


from keys import is_key_allowed


class TestIsKeyAllowed:
    """Tests for is_key_allowed function."""

    def test_exact_match_returns_1(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("00B5009EC1A8", keys) == 1

    def test_short_key_match_returns_1(self):
        keys = [{"key_number": "0000009EC1A8", "type": "normal"}]
        assert is_key_allowed("9EC1A8", keys) == 1

    def test_case_insensitive_match(self):
        keys = [{"key_number": "0000009EC1A8", "type": "normal"}]
        assert is_key_allowed("9ec1a8", keys) == 1

    def test_blocking_key_returns_1(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "blocking"}]
        assert is_key_allowed("00B5009EC1A8", keys) == 1

    def test_ibutton_full_match(self):
        keys = [{"key_number": "665544332211", "type": "normal"}]
        assert is_key_allowed("665544332211", keys) == 1

    def test_unknown_key_returns_0(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("000000000000", keys) == 0

    def test_empty_keys_returns_0(self):
        assert is_key_allowed("00B5009EC1A8", []) == 0

    def test_none_keys_returns_0(self):
        assert is_key_allowed("00B5009EC1A8", None) == 0

    def test_none_key_id_returns_0(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed(None, keys) == 0

    def test_empty_key_id_returns_0(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("", keys) == 0

    def test_string_json_key_in_list(self):
        keys = ['{"key_number": "00B5009EC1A8", "type": "normal"}']
        assert is_key_allowed("00B5009EC1A8", keys) == 1

    def test_broken_json_string_skipped(self):
        keys = ['not a json', {"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("00B5009EC1A8", keys) == 1

    def test_invalid_length_key_returns_0(self):
        keys = [{"key_number": "00B5009EC1A8", "type": "normal"}]
        assert is_key_allowed("00B5009EC1A8FF", keys) == 0
