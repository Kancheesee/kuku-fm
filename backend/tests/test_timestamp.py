import pytest
from app.services.timestamp import (
    extract_event_timing,
    format_ms_to_timestamp,
    parse_timestamp_to_ms,
)


def test_parse_timestamp_valid():
    assert parse_timestamp_to_ms("00:00.00") == 0
    assert parse_timestamp_to_ms("(00:01.80)") == 1800
    assert parse_timestamp_to_ms("01:10.50") == 70500
    assert parse_timestamp_to_ms("02:18.00") == 138000
    assert parse_timestamp_to_ms("1:05.25") == 65250
    # Hour boundary
    assert parse_timestamp_to_ms("01:00:00.00") == 3600000
    assert parse_timestamp_to_ms("01:02:03.50") == 3723500


def test_parse_timestamp_invalid_or_negative():
    assert parse_timestamp_to_ms("") is None
    assert parse_timestamp_to_ms("invalid") is None
    assert parse_timestamp_to_ms("-00:05.00") is None
    assert parse_timestamp_to_ms("00:60.00") is not None  # 60s handled mathematically


def test_format_ms_to_timestamp():
    assert format_ms_to_timestamp(0) == "00:00.00"
    assert format_ms_to_timestamp(1800) == "00:01.80"
    assert format_ms_to_timestamp(70500) == "01:10.50"
    assert format_ms_to_timestamp(3723500) == "01:02:03.50"
    assert format_ms_to_timestamp(-100) == "00:00.00"


def test_extract_event_timing():
    line = "Start: (00:16.80) | End: (00:18.50)"
    res = extract_event_timing(line)
    assert res == (16800, 18500)

    # Without parentheses
    line_no_paren = "Start: 00:02.10 | End: 00:05.40"
    assert extract_event_timing(line_no_paren) == (2100, 5400)

    # Malformed
    assert extract_event_timing("Start: malformed | End: 00:05.00") is None
    assert extract_event_timing("No timing here") is None

