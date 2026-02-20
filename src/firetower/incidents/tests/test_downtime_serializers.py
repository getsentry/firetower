"""Tests for downtime parsing in serializers."""

import pytest

from firetower.incidents.serializers import (
    format_downtime_seconds,
    parse_downtime_string,
)


class TestParseDowntimeString:
    """Test the parse_downtime_string utility function."""

    def test_parse_hours_only(self):
        """Test parsing hours only."""
        assert parse_downtime_string("1h") == 3600
        assert parse_downtime_string("2h") == 7200
        assert parse_downtime_string("24h") == 86400

    def test_parse_minutes_only(self):
        """Test parsing minutes only."""
        assert parse_downtime_string("1m") == 60
        assert parse_downtime_string("30m") == 1800
        assert parse_downtime_string("45m") == 2700

    def test_parse_seconds_only(self):
        """Test parsing seconds only."""
        assert parse_downtime_string("1s") == 1
        assert parse_downtime_string("30s") == 30
        assert parse_downtime_string("45s") == 45

    def test_parse_combined_hours_minutes(self):
        """Test parsing combined hours and minutes."""
        assert parse_downtime_string("1h 30m") == 5400
        assert parse_downtime_string("2h 15m") == 8100

    def test_parse_combined_all(self):
        """Test parsing combined hours, minutes, and seconds."""
        assert parse_downtime_string("1h 30m 45s") == 5445
        assert parse_downtime_string("2h 15m 30s") == 8130

    def test_parse_with_extra_whitespace(self):
        """Test parsing with extra whitespace."""
        assert parse_downtime_string("  1h  30m  ") == 5400
        assert parse_downtime_string("1h30m") == 5400

    def test_parse_case_insensitive(self):
        """Test case insensitive parsing."""
        assert parse_downtime_string("1H") == 3600
        assert parse_downtime_string("30M") == 1800
        assert parse_downtime_string("45S") == 45
        assert parse_downtime_string("1H 30M 45S") == 5445

    def test_parse_empty_string_raises_error(self):
        """Test that empty string raises error."""
        with pytest.raises(ValueError, match="Downtime string cannot be empty"):
            parse_downtime_string("")

        with pytest.raises(ValueError, match="Downtime string cannot be empty"):
            parse_downtime_string("   ")

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises error."""
        with pytest.raises(ValueError, match="Invalid downtime format"):
            parse_downtime_string("invalid")

        with pytest.raises(ValueError, match="Invalid downtime format"):
            parse_downtime_string("123")

        with pytest.raises(ValueError, match="Invalid downtime format"):
            parse_downtime_string("abc def")

    def test_parse_duplicate_units_raises_error(self):
        """Test that duplicate units raise error."""
        with pytest.raises(ValueError, match="Duplicate time unit 'h'"):
            parse_downtime_string("1h 2h")

        with pytest.raises(ValueError, match="Duplicate time unit 'm'"):
            parse_downtime_string("30m 15m")

        with pytest.raises(ValueError, match="Duplicate time unit 's'"):
            parse_downtime_string("10s 20s")


class TestFormatDowntimeSeconds:
    """Test the format_downtime_seconds utility function."""

    def test_format_hours_only(self):
        """Test formatting hours only."""
        assert format_downtime_seconds(3600) == "1h"
        assert format_downtime_seconds(7200) == "2h"
        assert format_downtime_seconds(86400) == "24h"

    def test_format_minutes_only(self):
        """Test formatting minutes only."""
        assert format_downtime_seconds(60) == "1m"
        assert format_downtime_seconds(1800) == "30m"
        assert format_downtime_seconds(2700) == "45m"

    def test_format_seconds_only(self):
        """Test formatting seconds only."""
        assert format_downtime_seconds(1) == "1s"
        assert format_downtime_seconds(30) == "30s"
        assert format_downtime_seconds(45) == "45s"

    def test_format_combined_hours_minutes(self):
        """Test formatting combined hours and minutes."""
        assert format_downtime_seconds(5400) == "1h 30m"
        assert format_downtime_seconds(8100) == "2h 15m"

    def test_format_combined_all(self):
        """Test formatting combined hours, minutes, and seconds."""
        assert format_downtime_seconds(5445) == "1h 30m 45s"
        assert format_downtime_seconds(8130) == "2h 15m 30s"

    def test_format_zero_seconds(self):
        """Test formatting zero seconds."""
        assert format_downtime_seconds(0) == "0s"

    def test_format_none_returns_none(self):
        """Test that None input returns None."""
        assert format_downtime_seconds(None) is None


class TestRoundtrip:
    """Test roundtrip conversion."""

    def test_parse_format_roundtrip(self):
        """Test that parse -> format -> parse produces same result."""
        test_cases = ["1h", "30m", "45s", "1h 30m", "2h 15m 30s"]

        for input_str in test_cases:
            seconds = parse_downtime_string(input_str)
            formatted = format_downtime_seconds(seconds)
            reparsed = parse_downtime_string(formatted)
            assert reparsed == seconds
