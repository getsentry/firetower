from unittest.mock import MagicMock, patch

import pytest
import requests

from firetower_sdk.client import FiretowerClient
from firetower_sdk.enums import IncidentSeverity, IncidentStatus, ServiceTier
from firetower_sdk.exceptions import FiretowerError


@pytest.fixture
def mock_jwt_interface():
    with patch("firetower_sdk.client.JWTInterface") as mock:
        mock_instance = MagicMock()
        mock_instance.get_signed_jwt.return_value = "fake-jwt-token"
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def client(mock_jwt_interface):
    return FiretowerClient(service_account="test@example.iam.gserviceaccount.com")


class TestFiretowerClientInit:
    def test_creates_session_with_auth(self, mock_jwt_interface):
        client = FiretowerClient(service_account="test@example.iam.gserviceaccount.com")
        assert client.session.auth is not None
        mock_jwt_interface.assert_called_once_with("test@example.iam.gserviceaccount.com")

    def test_default_base_url(self, mock_jwt_interface):
        client = FiretowerClient(service_account="test@example.iam.gserviceaccount.com")
        assert client.base_url == "https://firetower.getsentry.net"

    def test_custom_base_url(self, mock_jwt_interface):
        client = FiretowerClient(
            service_account="test@example.iam.gserviceaccount.com",
            base_url="https://custom.example.com/",
        )
        assert client.base_url == "https://custom.example.com"


class TestGetIncident:
    def test_success(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000", "title": "Test"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            result = client.get_incident("INC-2000")

            assert result == {"id": "INC-2000", "title": "Test"}
            mock_request.assert_called_once_with(
                method="GET",
                url="https://firetower.getsentry.net/api/incidents/INC-2000/",
                json=None,
                params=None,
                timeout=30,
            )

    def test_not_found(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Not found"
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock_response
            )
            mock_request.return_value = mock_response

            with pytest.raises(FiretowerError) as exc_info:
                client.get_incident("INC-9999")

            assert exc_info.value.status_code == 404


class TestCreateIncident:
    def test_success(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            result = client.create_incident(
                title="Test Incident",
                severity=IncidentSeverity.P1,
                captain_email="captain@example.com",
                reporter_email="reporter@example.com",
            )

            assert result == "INC-2000"
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"]["title"] == "Test Incident"
            assert call_kwargs["json"]["severity"] == "P1"
            assert call_kwargs["json"]["captain"] == "captain@example.com"
            assert call_kwargs["json"]["reporter"] == "reporter@example.com"

    def test_with_optional_fields(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            client.create_incident(
                title="Test Incident",
                severity="P1",
                captain_email="captain@example.com",
                reporter_email="reporter@example.com",
                description="Description",
                impact_summary="Impact",
                is_private=True,
            )

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"]["description"] == "Description"
            assert call_kwargs["json"]["impact_summary"] == "Impact"
            assert call_kwargs["json"]["is_private"] is True


class TestListIncidents:
    def test_basic_list(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [], "count": 0}
            mock_response.content = b'{"results": []}'
            mock_request.return_value = mock_response

            result = client.list_incidents()

            assert result == {"results": [], "count": 0}
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {"page": 1}

    def test_with_status_filter(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [], "count": 0}
            mock_response.content = b'{"results": []}'
            mock_request.return_value = mock_response

            client.list_incidents(
                statuses=[IncidentStatus.ACTIVE, IncidentStatus.MITIGATED], page=2
            )

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {"page": 2, "status": ["Active", "Mitigated"]}

    def test_with_date_filters(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [], "count": 0}
            mock_response.content = b'{"results": []}'
            mock_request.return_value = mock_response

            client.list_incidents(
                created_after="2024-01-01",
                created_before="2024-12-31",
            )

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {
                "page": 1,
                "created_after": "2024-01-01",
                "created_before": "2024-12-31",
            }

    def test_with_severity_filter(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [], "count": 0}
            mock_response.content = b'{"results": []}'
            mock_request.return_value = mock_response

            client.list_incidents(severities=[IncidentSeverity.P0, IncidentSeverity.P1], page=2)

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {"page": 2, "severity": ["P0", "P1"]}

    def test_with_tag_filters(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [], "count": 0}
            mock_response.content = b'{"results": []}'
            mock_request.return_value = mock_response

            client.list_incidents(
                affected_service=["API", "Database"],
                root_cause=["OOM"],
            )

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {
                "page": 1,
                "affected_service": ["API", "Database"],
                "root_cause": ["OOM"],
            }

    def test_with_service_tier_filter(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": [], "count": 0}
            mock_response.content = b'{"results": []}'
            mock_request.return_value = mock_response

            client.list_incidents(service_tiers=[ServiceTier.T0, ServiceTier.T1])

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["params"] == {
                "page": 1,
                "service_tier": ["T0", "T1"],
            }


class TestUpdateMethods:
    def test_update_status(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000", "status": "Mitigated"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            client.update_status("INC-2000", IncidentStatus.MITIGATED)

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"] == {"status": "Mitigated"}

    def test_update_severity(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000", "severity": "P0"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            client.update_severity("INC-2000", IncidentSeverity.P0)

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"] == {"severity": "P0"}

    def test_update_captain(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            client.update_captain("INC-2000", "newcaptain@example.com")

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"] == {"captain": "newcaptain@example.com"}

    def test_update_external_link(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            client.update_external_link("INC-2000", "slack", "https://slack.com/archives/C123")

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"] == {
                "external_links": {"slack": "https://slack.com/archives/C123"}
            }

    def test_update_incident_generic(self, client):
        with patch.object(client.session, "request") as mock_request:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "INC-2000"}
            mock_response.content = b'{"id": "INC-2000"}'
            mock_request.return_value = mock_response

            client.update_incident("INC-2000", status="Done", severity="P2")

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["json"] == {"status": "Done", "severity": "P2"}


class TestAppendDescription:
    def test_append_to_existing(self, client):
        with patch.object(client.session, "request") as mock_request:
            get_response = MagicMock()
            get_response.json.return_value = {"id": "INC-2000", "description": "Original"}
            get_response.content = b'{"description": "Original"}'

            patch_response = MagicMock()
            patch_response.json.return_value = {"id": "INC-2000"}
            patch_response.content = b'{"id": "INC-2000"}'

            mock_request.side_effect = [get_response, patch_response]

            client.append_description("INC-2000", "Appended text")

            patch_call = mock_request.call_args_list[1]
            assert patch_call[1]["json"] == {"description": "Original\n\nAppended text"}

    def test_append_to_empty(self, client):
        with patch.object(client.session, "request") as mock_request:
            get_response = MagicMock()
            get_response.json.return_value = {"id": "INC-2000", "description": None}
            get_response.content = b'{"description": null}'

            patch_response = MagicMock()
            patch_response.json.return_value = {"id": "INC-2000"}
            patch_response.content = b'{"id": "INC-2000"}'

            mock_request.side_effect = [get_response, patch_response]

            client.append_description("INC-2000", "First text")

            patch_call = mock_request.call_args_list[1]
            assert patch_call[1]["json"] == {"description": "First text"}
