import pytest

from firetower_sdk.utils import (
    FIRETOWER_ID_CUTOFF,
    get_firetower_url,
    is_firetower_incident_id,
)


class TestIsFiretowerIncidentId:
    def test_integer_above_cutoff(self):
        assert is_firetower_incident_id(2000) is True
        assert is_firetower_incident_id(2001) is True
        assert is_firetower_incident_id(9999) is True

    def test_integer_below_cutoff(self):
        assert is_firetower_incident_id(1999) is False
        assert is_firetower_incident_id(1) is False
        assert is_firetower_incident_id(0) is False

    def test_string_above_cutoff(self):
        assert is_firetower_incident_id("INC-2000") is True
        assert is_firetower_incident_id("INC-2001") is True
        assert is_firetower_incident_id("TESTINC-3000") is True

    def test_string_below_cutoff(self):
        assert is_firetower_incident_id("INC-1999") is False
        assert is_firetower_incident_id("INC-1") is False

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid incident ID format"):
            is_firetower_incident_id("invalid")

        with pytest.raises(ValueError, match="Invalid incident ID format"):
            is_firetower_incident_id("INC2000")

    def test_cutoff_value(self):
        assert FIRETOWER_ID_CUTOFF == 2000


class TestGetFiretowerUrl:
    def test_default_base_url(self):
        url = get_firetower_url("INC-2000")
        assert url == "https://firetower.getsentry.net/INC-2000"

    def test_custom_base_url(self):
        url = get_firetower_url("INC-2000", base_url="https://test.firetower.example.com")
        assert url == "https://test.firetower.example.com/INC-2000"

    def test_trailing_slash_stripped(self):
        url = get_firetower_url("INC-2000", base_url="https://example.com/")
        assert url == "https://example.com/INC-2000"
