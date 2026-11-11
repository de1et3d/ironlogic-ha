"""Tests for key display formatting (sensor logic)."""



def format_key_display(key, key_name=None, event_code=None, current=None):
    """Standalone copy of the sensor formatting logic for testing."""
    if event_code in (0x08, 0x09):
        return "Network"

    if event_code in (0x0C, 0x0D, 0x20, 0x21, 0x22, 0x23, 0x0E, 0x0F):
        return current

    short = key[-6:] if key and len(key) > 6 else (key or "")
    has_name = (
        key_name and key_name not in ("Unknown", "Unknown key", "unnamed")
    )

    if event_code in (0x02, 0x03, 0x06, 0x07):
        if key and key != "000000000000":
            if event_code in (0x02, 0x03):
                status = "not found"
            else:
                status = "denied"
            if has_name:
                return f"{key_name} ({short}, {status})"
            return f"{short} ({status})"
        return "Unknown key"

    if event_code in (0x04, 0x05):
        if has_name:
            return f"{key_name} ({short})"
        if key and key != "000000000000":
            return f"{short} (granted)"
        return "No keys yet"

    if has_name:
        return f"{key_name} ({short})"
    if key and key != "000000000000":
        return short
    return "No keys yet"


class TestFormatKeyDisplay:
    """Tests for key display formatting."""

    def test_network_event(self):
        assert format_key_display("000000386753", None, 0x08) == "Network"
        assert format_key_display("000000386753", None, 0x09) == "Network"

    def test_granted_with_name(self):
        assert format_key_display("000000386753", "John", 0x04) == "John (386753)"

    def test_granted_without_name(self):
        assert format_key_display("000000386753", None, 0x04) == "386753 (granted)"

    def test_denied_with_name(self):
        result = format_key_display("000000386753", "John", 0x06)
        assert result == "John (386753, denied)"

    def test_denied_without_name(self):
        result = format_key_display("000000386753", None, 0x06)
        assert result == "386753 (denied)"

    def test_not_found_with_name(self):
        result = format_key_display("00000033757B", "Some", 0x02)
        assert result == "Some (33757B, not found)"

    def test_not_found_without_name(self):
        result = format_key_display("00000033757B", None, 0x02)
        assert result == "33757B (not found)"

    def test_unknown_key_id_zero(self):
        assert format_key_display("000000000000", None, 0x04) == "No keys yet"

    def test_ibutton_full_id_shows_last_6(self):
        result = format_key_display("665544332211", "iButton", 0x04)
        assert result == "iButton (332211)"

    def test_door_event_uses_current(self):
        result = format_key_display(
            "000000386753", None, 0x20, current="Door opened"
        )
        assert result == "Door opened"

    def test_unnamed_name_ignored(self):
        result = format_key_display("000000386753", "unnamed", 0x04)
        assert result == "386753 (granted)"

    def test_unknown_name_ignored(self):
        result = format_key_display("000000386753", "Unknown", 0x04)
        assert result == "386753 (granted)"