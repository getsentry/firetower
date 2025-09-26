from unittest.mock import patch

import pytest
from django.conf import settings

from .services.jira import JiraService


class TestJiraService:
    """Test suite for JiraService"""

    def test_initialization_requires_credentials(self):
        """Test that JiraService initialization validates required credentials"""
        # Mock settings to have empty credentials
        mock_jira_config = {
            "ACCOUNT": "",
            "API_KEY": "",
            "DOMAIN": "https://test.atlassian.net",
            "PROJECT_KEY": "INC",
            "SEVERITY_FIELD": "customfield_10001",
        }

        with patch.object(settings, "JIRA", mock_jira_config):
            with pytest.raises(ValueError, match="Jira credentials not configured"):
                JiraService()
