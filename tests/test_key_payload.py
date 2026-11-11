"""Tests for build_key_payload function."""


from keys import build_key_payload


class TestBuildKeyPayload:
    """Tests for build_key_payload function."""

    def test_normal_key(self):
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
        key_data = {
            "key_number": "00B5009EC1A8",
            "name": "Master Key",
            "type": "master",
            "flags": 0,
        }
        card = build_key_payload(key_data)
        assert card is None

    def test_payload_uses_card_field(self):
        """Verify payload uses "card" field (Web-JSON protocol)."""
        key_data = {
            "key_number": "00B5009EC1A8",
            "type": "normal",
            "flags": 0,
        }
        card = build_key_payload(key_data)
        assert "card" in card
        assert "key" not in card

    def test_ibutton_key(self):
        key_data = {
            "key_number": "665544332211",
            "type": "normal",
            "flags": 0,
        }
        card = build_key_payload(key_data)
        assert card is not None
        assert card["card"] == "665544332211"