"""
Basic pytest tests for Jira integration service.
"""
import os
import pytest
from unittest.mock import patch
from .services.jira import JiraService


# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firetower.settings')

import django
from django.conf import settings

# Setup Django
django.setup()


class TestJiraService:
    """Test suite for JiraService"""
    
    def test_initialization_requires_credentials(self):
        """Test that JiraService initialization validates required credentials."""
        # Mock settings to have empty credentials
        mock_jira_config = {
            'ACCOUNT': '',
            'API_KEY': '',
            'DOMAIN': 'https://test.atlassian.net',
            'PROJECT_KEY': 'INC',
            'SEVERITY_FIELD': 'customfield_10001'
        }
        
        with patch.object(settings, 'JIRA', mock_jira_config):
            with pytest.raises(ValueError, match="Jira credentials not configured"):
                JiraService()

    def test_initialization_success_with_valid_credentials(self):
        """Test that JiraService initializes successfully with valid credentials."""
        mock_jira_config = {
            'ACCOUNT': 'test@example.com',
            'API_KEY': 'test-api-key',
            'DOMAIN': 'https://test.atlassian.net',
            'PROJECT_KEY': 'INC',
            'SEVERITY_FIELD': 'customfield_10001'
        }
        
        with patch.object(settings, 'JIRA', mock_jira_config):
            with patch('firetower.integrations.services.jira.JIRA') as mock_jira_client:
                service = JiraService()
                
                # Verify the service was created and JIRA client was initialized
                assert service.domain == 'https://test.atlassian.net'
                assert service.project_key == 'INC'
                assert service.severity_field_id == 'customfield_10001'
                mock_jira_client.assert_called_once()

    def test_extract_severity_with_valid_field(self):
        """Test severity extraction from Jira issue with valid severity field."""
        mock_jira_config = {
            'ACCOUNT': 'test@example.com',
            'API_KEY': 'test-api-key',
            'DOMAIN': 'https://test.atlassian.net',
            'PROJECT_KEY': 'INC',
            'SEVERITY_FIELD': 'customfield_10001'
        }
        
        with patch.object(settings, 'JIRA', mock_jira_config):
            with patch('firetower.integrations.services.jira.JIRA'):
                service = JiraService()
                
                # Mock issue with severity field
                mock_issue = type('MockIssue', (), {})()
                mock_issue.fields = type('MockFields', (), {})()
                mock_severity = type('MockSeverity', (), {'value': 'P1'})()
                setattr(mock_issue.fields, 'customfield_10001', mock_severity)
                
                severity = service._extract_severity(mock_issue)
                assert severity == 'P1'

    def test_extract_severity_with_missing_field(self):
        """Test severity extraction when severity field is missing."""
        mock_jira_config = {
            'ACCOUNT': 'test@example.com',
            'API_KEY': 'test-api-key',
            'DOMAIN': 'https://test.atlassian.net',
            'PROJECT_KEY': 'INC',
            'SEVERITY_FIELD': 'customfield_10001'
        }
        
        with patch.object(settings, 'JIRA', mock_jira_config):
            with patch('firetower.integrations.services.jira.JIRA'):
                service = JiraService()
                
                # Mock issue without severity field
                mock_issue = type('MockIssue', (), {})()
                mock_issue.fields = type('MockFields', (), {})()
                
                severity = service._extract_severity(mock_issue)
                assert severity is None

    def test_get_incidents_validates_status_format(self):
        """Test that get_incidents validates status parameter format."""
        mock_jira_config = {
            'ACCOUNT': 'test@example.com',
            'API_KEY': 'test-api-key',
            'DOMAIN': 'https://test.atlassian.net',
            'PROJECT_KEY': 'INC',
            'SEVERITY_FIELD': 'customfield_10001'
        }
        
        with patch.object(settings, 'JIRA', mock_jira_config):
            with patch('firetower.integrations.services.jira.JIRA'):
                service = JiraService()
                
                # Test with invalid characters in status
                with pytest.raises(ValueError, match="Invalid status format"):
                    service.get_incidents(status="Active; DROP TABLE incidents;")
                
                # Test with numbers in status
                with pytest.raises(ValueError, match="Invalid status format"):
                    service.get_incidents(status="Status123")

    def test_get_incidents_builds_correct_jql_query(self):
        """Test that get_incidents builds the correct JQL query."""
        mock_jira_config = {
            'ACCOUNT': 'test@example.com',
            'API_KEY': 'test-api-key',
            'DOMAIN': 'https://test.atlassian.net',
            'PROJECT_KEY': 'TESTINC',
            'SEVERITY_FIELD': 'customfield_10001'
        }
        
        with patch.object(settings, 'JIRA', mock_jira_config):
            with patch('firetower.integrations.services.jira.JIRA') as mock_jira_client:
                mock_client_instance = mock_jira_client.return_value
                mock_client_instance.search_issues.return_value = []
                
                service = JiraService()
                
                # Test without status filter
                service.get_incidents()
                expected_jql = 'project = "TESTINC" ORDER BY created DESC'
                mock_client_instance.search_issues.assert_called_with(
                    expected_jql, 
                    maxResults=50,
                    expand='changelog'
                )
                
                # Test with status filter
                service.get_incidents(status="Active")
                expected_jql_with_status = 'project = "TESTINC" AND status = "Active" ORDER BY created DESC'
                mock_client_instance.search_issues.assert_called_with(
                    expected_jql_with_status,
                    maxResults=50,
                    expand='changelog'
                )
