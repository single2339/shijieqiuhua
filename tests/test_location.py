"""Tests for geographic location normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.processors.location import extract_location, extract_location_with_fallback
from backend.osint_sources import _COUNTRY_COORDS


class _Doc:
    extensions = {
        "horizon_metadata": {
            "location_country": "Taiwan",
            "location_city": "Taipei",
        }
    }


def test_taiwan_text_normalizes_to_china_taiwan_province():
    assert extract_location("台湾 semiconductor supply chain update") == (
        "中国台湾省",
        "台湾省",
        25.0330,
        121.5654,
    )


def test_taipei_text_normalizes_to_china_taiwan_province():
    country, city, lat, lng = extract_location("Taipei reports new cyber policy")
    assert country == "中国台湾省"
    assert city == "台湾省"
    assert lat == 25.0330
    assert lng == 121.5654


def test_stored_taiwan_location_normalizes_to_china_taiwan_province():
    assert extract_location_with_fallback("", doc=_Doc()) == (
        "中国台湾省",
        "台湾省",
        25.0330,
        121.5654,
    )


def test_source_country_taiwan_focus_normalizes_to_china_taiwan_province():
    # SourceConfig country_focus values are looked up in this coordinate table.
    assert _COUNTRY_COORDS["Taiwan"] == (
        "中国台湾省",
        "台湾省",
        25.0330,
        121.5654,
    )
