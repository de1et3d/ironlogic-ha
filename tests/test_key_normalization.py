"""Tests for key number normalization and short display."""

import pytest

from keys import normalize_key_number, short_key_number


class TestNormalizeKeyNumber:
    """Tests for normalize_key_number function."""

    def test_12_chars_no_prefix(self):
        assert normalize_key_number("00B5009EC1A8") == "00B5009EC1A8"

    def test_14_chars_with_0x_prefix_rejected(self):
        assert normalize_key_number("0x00B5009EC1A8") == ""

    def test_14_chars_with_0X_prefix_rejected(self):
        assert normalize_key_number("0X00B5009EC1A8") == ""

    def test_13_chars_rejected(self):
        assert normalize_key_number("000B5009EC1A8") == ""

    def test_10_chars_padded_with_zeros(self):
        assert normalize_key_number("B5009EC1A8") == "00B5009EC1A8"

    def test_8_chars_padded_with_zeros(self):
        assert normalize_key_number("9EC1A8") == "0000009EC1A8"

    def test_6_chars_padded_to_12(self):
        assert normalize_key_number("9EC1A8") == "0000009EC1A8"

    def test_7_chars_padded_to_12(self):
        assert normalize_key_number("09EC1A8") == "000009EC1A8"

    def test_lowercase_converted_to_uppercase(self):
        assert normalize_key_number("00b5009ec1a8") == "00B5009EC1A8"

    def test_whitespace_stripped(self):
        assert normalize_key_number(" 00B5009EC1A8 ") == "00B5009EC1A8"

    def test_whitespace_inside_removed(self):
        assert normalize_key_number("00B5 009E C1A8") == "00B5009EC1A8"

    def test_dashes_not_removed(self):
        assert normalize_key_number("00-B5-00-9E-C1-A8") == ""

    def test_empty_string_returns_empty(self):
        assert normalize_key_number("") == ""

    def test_none_returns_empty(self):
        assert normalize_key_number(None) == ""

    def test_ibutton_full_12_chars(self):
        assert normalize_key_number("665544332211") == "665544332211"


class TestShortKeyNumber:
    """Tests for short_key_number function."""

    def test_returns_last_6_chars(self):
        assert short_key_number("00B5009EC1A8") == "9EC1A8"

    def test_exactly_6_chars_returns_same(self):
        assert short_key_number("9EC1A8") == "9EC1A8"

    def test_12_chars_returns_last_6(self):
        assert short_key_number("0000009EC1A8") == "9EC1A8"

    def test_returns_full_string_if_shorter_than_6(self):
        assert short_key_number("ABC") == "ABC"

    def test_returns_empty_for_empty(self):
        assert short_key_number("") == ""

    def test_returns_empty_for_none(self):
        assert short_key_number(None) == ""

    def test_ibutton_returns_last_6(self):
        assert short_key_number("665544332211") == "332211"