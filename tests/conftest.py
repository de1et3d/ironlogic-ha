"""Pytest configuration for IronLogic integration tests."""

import os
import sys

import pytest

COMPONENT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "ironlogic"
)
sys.path.insert(0, os.path.abspath(COMPONENT_DIR))


@pytest.fixture
def sample_keys():
    """Sample list of allowed keys."""
    return [
        {
            "key_number": "00B5009EC1A8",
            "name": "John",
            "type": "normal",
            "flags": 0,
            "added_at": "2026-01-01 10:00:00",
            "last_used": None,
        },
        {
            "key_number": "000000BB076B",
            "name": "Guest",
            "type": "blocking",
            "flags": 8,
            "added_at": "2026-01-02 11:00:00",
            "last_used": None,
        },
        {
            "key_number": "665544332211",
            "name": "iButton",
            "type": "normal",
            "flags": 0,
            "added_at": "2026-01-03 12:00:00",
            "last_used": None,
        },
    ]
