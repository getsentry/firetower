from unittest.mock import MagicMock, patch

from django.conf import settings

from .services.statuspage import StatuspageService

MOCK_STATUSPAGE_CONFIG = {
    "API_KEY": "test-api-key",
    "PAGE_ID": "test-page-id",
    "URL": "https://test.statuspage.io/",
}


class TestStatuspageServiceInit:
    def test_init_with_config(self):
        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()
            assert service.configured is True
            assert service.api_key == "test-api-key"
            assert service.page_id == "test-page-id"
            assert service.base_url == "https://test.statuspage.io/"

    def test_init_without_config(self):
        with patch.object(settings, "STATUSPAGE", None):
            service = StatuspageService()
            assert service.configured is False

    def test_init_with_empty_api_key(self):
        config = {**MOCK_STATUSPAGE_CONFIG, "API_KEY": ""}
        with patch.object(settings, "STATUSPAGE", config):
            service = StatuspageService()
            assert service.configured is False


class TestStatuspageServiceGetComponents:
    def test_get_components_groups_hierarchy(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "parent1", "name": "API", "group_id": None, "position": 1},
            {"id": "child1", "name": "REST API", "group_id": "parent1", "position": 1},
            {
                "id": "child2",
                "name": "GraphQL API",
                "group_id": "parent1",
                "position": 2,
            },
            {"id": "standalone", "name": "Website", "group_id": None, "position": 0},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.get",
            return_value=mock_response,
        ) as mock_get:
            top_level, children_map = service.get_components()

            mock_get.assert_called_once()
            assert len(top_level) == 2
            assert top_level[0]["id"] in ("parent1", "standalone")
            assert len(children_map["parent1"]) == 2
            assert "standalone" not in children_map

    def test_get_components_empty(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.get",
            return_value=mock_response,
        ):
            top_level, children_map = service.get_components()
            assert top_level == []
            assert len(children_map) == 0


class TestStatuspageServiceGetIncident:
    def test_get_incident_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "abc123",
            "name": "Test Incident",
            "status": "investigating",
        }

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.get",
            return_value=mock_response,
        ) as mock_get:
            result = service.get_incident("abc123")

            assert result is not None
            assert result["id"] == "abc123"
            assert result["name"] == "Test Incident"
            mock_get.assert_called_once_with(
                "https://api.statuspage.io/v1/pages/test-page-id/incidents/abc123",
                headers=service._headers(),
            )

    def test_get_incident_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.get",
            return_value=mock_response,
        ):
            result = service.get_incident("nonexistent")
            assert result is None


class TestStatuspageServiceCreateIncident:
    def test_create_incident_basic(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new123", "name": "Outage"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = service.create_incident(
                title="Outage",
                status="investigating",
                message="Looking into it",
            )

            assert result["id"] == "new123"
            call_kwargs = mock_post.call_args
            payload = call_kwargs[1]["json"]
            assert payload["incident"]["name"] == "Outage"
            assert payload["incident"]["status"] == "investigating"
            assert payload["incident"]["body"] == "Looking into it"
            assert payload["incident"]["impact"] == "major"
            assert payload["incident"]["deliver_notifications"] is True

    def test_create_incident_with_components_and_impact(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new456"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.post",
            return_value=mock_response,
        ) as mock_post:
            service.create_incident(
                title="Outage",
                status="investigating",
                message="Looking into it",
                impact="critical",
                components={"comp1": "major_outage"},
            )

            payload = mock_post.call_args[1]["json"]
            assert payload["incident"]["impact"] == "critical"
            assert payload["incident"]["components"] == {"comp1": "major_outage"}

    def test_create_incident_raises_on_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("API error")

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.post",
            return_value=mock_response,
        ):
            try:
                service.create_incident("title", "investigating", "msg")
                assert False, "Should have raised"
            except Exception:
                pass


class TestStatuspageServiceUpdateIncident:
    def test_update_incident_status_and_message(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "inc123", "status": "identified"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.patch",
            return_value=mock_response,
        ) as mock_patch:
            result = service.update_incident(
                incident_id="inc123",
                status="identified",
                message="Found the issue",
            )

            assert result["status"] == "identified"
            call_kwargs = mock_patch.call_args
            assert "incidents/inc123" in call_kwargs[0][0]
            payload = call_kwargs[1]["json"]
            assert payload["incident"]["status"] == "identified"
            assert payload["incident"]["body"] == "Found the issue"

    def test_update_incident_with_components(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "inc123"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.patch",
            return_value=mock_response,
        ) as mock_patch:
            service.update_incident(
                incident_id="inc123",
                components={"comp1": "degraded_performance"},
            )

            payload = mock_patch.call_args[1]["json"]
            assert payload["incident"]["components"] == {
                "comp1": "degraded_performance"
            }

    def test_update_incident_minimal(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "inc123"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()

        with patch(
            "firetower.integrations.services.statuspage.requests.patch",
            return_value=mock_response,
        ) as mock_patch:
            service.update_incident(incident_id="inc123")

            payload = mock_patch.call_args[1]["json"]
            assert "status" not in payload["incident"]
            assert "body" not in payload["incident"]
            assert "components" not in payload["incident"]
            assert payload["incident"]["deliver_notifications"] is True


class TestStatuspageServiceUrlHelpers:
    def test_get_incident_url(self):
        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()
        assert (
            service.get_incident_url("abc123")
            == "https://test.statuspage.io/incidents/abc123"
        )

    def test_extract_incident_id_from_url(self):
        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()
        assert (
            service.extract_incident_id_from_url(
                "https://test.statuspage.io/incidents/abc123"
            )
            == "abc123"
        )

    def test_extract_incident_id_from_url_trailing_slash(self):
        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()
        assert (
            service.extract_incident_id_from_url(
                "https://test.statuspage.io/incidents/abc123/"
            )
            == "abc123"
        )

    def test_extract_incident_id_from_empty_url(self):
        with patch.object(settings, "STATUSPAGE", MOCK_STATUSPAGE_CONFIG):
            service = StatuspageService()
        assert service.extract_incident_id_from_url("") is None
