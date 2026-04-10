from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from firetower.auth.models import ExternalProfile, ExternalProfileType
from firetower.incidents.hooks import (
    _build_channel_name,
    _build_channel_topic,
    _page_high_sev_if_needed,
    on_captain_changed,
    on_incident_created,
    on_severity_changed,
    on_status_changed,
    on_title_changed,
    on_visibility_changed,
)
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


@pytest.mark.django_db
class TestBuildChannelName:
    def test_format(self):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )
        assert _build_channel_name(incident) == incident.incident_number.lower()


@pytest.mark.django_db
class TestBuildChannelTopic:
    def test_format_with_captain_slack_profile(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        ExternalProfile.objects.create(
            user=captain,
            type=ExternalProfileType.SLACK,
            external_id="U_CAPTAIN",
        )
        incident = Incident.objects.create(
            title="Database connection pool exhausted",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        topic = _build_channel_topic(incident)
        assert topic.startswith("[P1] ")
        assert (
            f"|{incident.incident_number} Database connection pool exhausted>" in topic
        )
        assert "| IC: <@U_CAPTAIN>" in topic

    def test_format_with_captain_no_slack_profile(self):
        captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Doe",
        )
        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        topic = _build_channel_topic(incident)
        assert "| IC: Jane Doe" in topic

    def test_format_without_captain(self):
        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P2,
        )
        topic = _build_channel_topic(incident)
        assert topic.startswith("[P2] ")
        assert f"|{incident.incident_number} Test Incident>" in topic
        assert "IC:" not in topic

    def test_long_title_is_truncated(self):
        long_title = "A" * 300
        incident = Incident.objects.create(
            title=long_title,
            severity=IncidentSeverity.P1,
        )
        topic = _build_channel_topic(incident)
        assert len(topic) <= 250
        assert "\u2026" in topic

    def test_special_chars_in_title_do_not_exceed_max_length(self):
        # A title full of '&' chars: each expands to '&amp;' (5 chars).
        # Escaping must happen before truncation so the result stays within budget.
        long_title = "&" * 300
        incident = Incident.objects.create(
            title=long_title,
            severity=IncidentSeverity.P1,
        )
        topic = _build_channel_topic(incident)
        assert len(topic) <= 250
        # The topic must be a well-formed Slack link — closing '>' must be present.
        assert ">" in topic


@pytest.mark.django_db
class TestOnIncidentCreated:
    def setup_method(self):
        self.captain = User.objects.create_user(
            username="captain@example.com",
            email="captain@example.com",
            first_name="Jane",
            last_name="Captain",
        )
        self.reporter = User.objects.create_user(
            username="reporter@example.com",
            email="reporter@example.com",
        )

    @patch("firetower.incidents.hooks._slack_service")
    def test_creates_channel_and_link(self, mock_slack):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
            reporter=self.reporter,
        )

        on_incident_created(incident)

        mock_slack.create_channel.assert_called_once_with(
            incident.incident_number.lower(), is_private=False
        )
        link = ExternalLink.objects.get(incident=incident, type=ExternalLinkType.SLACK)
        assert link.url == "https://slack.com/archives/C99999"
        mock_slack.set_channel_topic.assert_called_once()
        mock_slack.add_bookmark.assert_called_once()
        mock_slack.post_message.assert_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_skips_if_slack_link_exists(self, mock_slack):
        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C00000",
        )

        on_incident_created(incident)

        mock_slack.create_channel.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_handles_create_channel_failure(self, mock_slack):
        mock_slack.create_channel.return_value = None

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
        )

        on_incident_created(incident)

        assert not ExternalLink.objects.filter(
            incident=incident, type=ExternalLinkType.SLACK
        ).exists()

    @patch("firetower.incidents.hooks._slack_service")
    def test_invites_captain_with_slack_profile(self, mock_slack):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        ExternalProfile.objects.create(
            user=self.captain,
            type=ExternalProfileType.SLACK,
            external_id="U_CAPTAIN",
        )

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )

        on_incident_created(incident)

        mock_slack.invite_to_channel.assert_called_once_with("C99999", ["U_CAPTAIN"])

    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_to_feed_channel(self, mock_slack, settings):
        settings.SLACK["INCIDENT_FEED_CHANNEL_ID"] = "C_FEED"
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )

        on_incident_created(incident)

        feed_calls = [
            c for c in mock_slack.post_message.call_args_list if c[0][0] == "C_FEED"
        ]
        assert len(feed_calls) == 1
        assert "P1" in feed_calls[0][0][1]

    @patch("firetower.incidents.hooks._slack_service")
    def test_private_incident_skips_feed_channel(self, mock_slack, settings):
        settings.SLACK["INCIDENT_FEED_CHANNEL_ID"] = "C_FEED"
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Secret Incident",
            severity=IncidentSeverity.P1,
            is_private=True,
        )

        on_incident_created(incident)

        feed_calls = [
            c for c in mock_slack.post_message.call_args_list if c[0][0] == "C_FEED"
        ]
        assert len(feed_calls) == 0

    @patch("firetower.incidents.hooks._slack_service")
    def test_invites_always_invited_ids(self, mock_slack, settings):
        settings.SLACK["ALWAYS_INVITED_IDS"] = ["U_SRE1", "U_SRE2"]
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
        )

        on_incident_created(incident)

        mock_slack.invite_to_channel.assert_called_once_with(
            "C99999", ["U_SRE1", "U_SRE2"]
        )

    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_guide_message(self, mock_slack, settings):
        settings.SLACK["INCIDENT_GUIDE_MESSAGE"] = "Here is the guide."
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
        )

        on_incident_created(incident)

        first_message = mock_slack.post_message.call_args_list[0]
        assert first_message[0][0] == "C99999"
        assert first_message[0][1] == "Here is the guide."

    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_description_when_present(self, mock_slack):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            description="Something is broken",
        )

        on_incident_created(incident)

        desc_calls = [
            c
            for c in mock_slack.post_message.call_args_list
            if "Incident Description" in c[0][1]
        ]
        assert len(desc_calls) == 1
        assert "Something is broken" in desc_calls[0][0][1]

    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_ic_in_channel_message(self, mock_slack):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        ExternalProfile.objects.create(
            user=self.captain,
            type=ExternalProfileType.SLACK,
            external_id="U_CAPTAIN",
        )

        incident = Incident.objects.create(
            title="Test Incident",
            severity=IncidentSeverity.P1,
            captain=self.captain,
        )

        on_incident_created(incident)

        info_calls = [
            c
            for c in mock_slack.post_message.call_args_list
            if c[0][0] == "C99999" and "Incident Captain:" in c[0][1]
        ]
        assert len(info_calls) == 1
        assert "Incident Captain: <@U_CAPTAIN>" in info_calls[0][0][1]


@pytest.mark.django_db
class TestOnStatusChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_status_update_message(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            status=IncidentStatus.MITIGATED,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_status_changed(incident, IncidentStatus.ACTIVE)

        mock_slack.post_message.assert_called_once()
        assert "Active" in mock_slack.post_message.call_args[0][1]
        assert "Mitigated" in mock_slack.post_message.call_args[0][1]
        mock_slack.set_channel_topic.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_status_changed(incident, IncidentStatus.ACTIVE)

        mock_slack.post_message.assert_not_called()


@pytest.mark.django_db
class TestOnSeverityChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_severity_update_message(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P0,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_severity_changed(incident, IncidentSeverity.P2)

        mock_slack.post_message.assert_called_once()
        assert "P2" in mock_slack.post_message.call_args[0][1]
        assert "P0" in mock_slack.post_message.call_args[0][1]
        mock_slack.set_channel_topic.assert_called_once()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_severity_changed(incident, IncidentSeverity.P2)

        mock_slack.post_message.assert_not_called()


@pytest.mark.django_db
class TestOnTitleChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_updates_topic(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Updated Title",
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_title_changed(incident)

        mock_slack.set_channel_topic.assert_called_once()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_title_changed(incident)

        mock_slack.set_channel_topic.assert_not_called()


@pytest.mark.django_db
class TestOnVisibilityChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_private_message(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            is_private=True,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_visibility_changed(incident)

        mock_slack.post_message.assert_called_once()
        msg = mock_slack.post_message.call_args[0][1]
        assert "private" in msg

    @patch("firetower.incidents.hooks._slack_service")
    def test_posts_public_message(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            is_private=False,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_visibility_changed(incident)

        mock_slack.post_message.assert_called_once()
        msg = mock_slack.post_message.call_args[0][1]
        assert "public" in msg

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_visibility_changed(incident)

        mock_slack.post_message.assert_not_called()


@pytest.mark.django_db
class TestOnCaptainChanged:
    @patch("firetower.incidents.hooks._slack_service")
    def test_updates_topic_and_invites(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        captain = User.objects.create_user(
            username="newcaptain@example.com",
            email="newcaptain@example.com",
            first_name="New",
            last_name="Captain",
        )
        ExternalProfile.objects.create(
            user=captain,
            type=ExternalProfileType.SLACK,
            external_id="U_NEW",
        )

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_captain_changed(incident)

        mock_slack.set_channel_topic.assert_called_once()
        mock_slack.post_message.assert_called_once()
        assert "<@U_NEW>" in mock_slack.post_message.call_args[0][1]
        mock_slack.invite_to_channel.assert_called_once_with("C12345", ["U_NEW"])

    @patch("firetower.incidents.hooks._slack_service")
    def test_updates_topic_and_posts_name_when_no_slack_profile(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        captain = User.objects.create_user(
            username="newcaptain@example.com",
            email="newcaptain@example.com",
            first_name="New",
            last_name="Captain",
        )

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            captain=captain,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_captain_changed(incident)

        mock_slack.set_channel_topic.assert_called_once()
        mock_slack.post_message.assert_called_once()
        assert "New Captain" in mock_slack.post_message.call_args[0][1]

    @patch("firetower.incidents.hooks._slack_service")
    def test_updates_topic_only_when_captain_cleared(self, mock_slack):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
            captain=None,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_captain_changed(incident)

        mock_slack.set_channel_topic.assert_called_once()
        mock_slack.post_message.assert_not_called()

    @patch("firetower.incidents.hooks._slack_service")
    def test_noop_without_slack_link(self, mock_slack):
        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P1,
        )

        on_captain_changed(incident)

        mock_slack.set_channel_topic.assert_not_called()


MOCK_PD_CONFIG = {
    "API_TOKEN": "test-token",
    "ESCALATION_POLICIES": {
        "HIGH_SEV": {
            "id": "P17I207",
            "integration_key": "test-integration-key",
        },
    },
}


@pytest.mark.django_db
class TestPageHighSevIfNeeded:
    @patch("firetower.incidents.hooks.PagerDutyService")
    def test_pages_for_p0(self, mock_pd_cls, settings):
        settings.PAGERDUTY = MOCK_PD_CONFIG
        settings.FIRETOWER_BASE_URL = "https://firetower.example.com"
        mock_pd = mock_pd_cls.return_value
        mock_pd.trigger_incident.return_value = True

        incident = Incident.objects.create(
            title="Major outage",
            severity=IncidentSeverity.P0,
        )

        _page_high_sev_if_needed(incident)

        mock_pd.trigger_incident.assert_called_once_with(
            f"[P0] {incident.incident_number}: Major outage",
            f"firetower-{incident.incident_number}",
            "test-integration-key",
            links=[
                {
                    "href": f"https://firetower.example.com/{incident.incident_number}",
                    "text": "View in Firetower",
                }
            ],
        )

    @patch("firetower.incidents.hooks.PagerDutyService")
    def test_pages_for_p1(self, mock_pd_cls, settings):
        settings.PAGERDUTY = MOCK_PD_CONFIG
        mock_pd = mock_pd_cls.return_value
        mock_pd.trigger_incident.return_value = True

        incident = Incident.objects.create(
            title="Service degradation",
            severity=IncidentSeverity.P1,
        )

        _page_high_sev_if_needed(incident)

        mock_pd.trigger_incident.assert_called_once()

    @patch("firetower.incidents.hooks.PagerDutyService")
    def test_skips_for_p2(self, mock_pd_cls, settings):
        settings.PAGERDUTY = MOCK_PD_CONFIG

        incident = Incident.objects.create(
            title="Minor issue",
            severity=IncidentSeverity.P2,
        )

        _page_high_sev_if_needed(incident)

        mock_pd_cls.assert_not_called()

    @patch("firetower.incidents.hooks.PagerDutyService")
    def test_skips_when_pagerduty_not_configured(self, mock_pd_cls, settings):
        settings.PAGERDUTY = None

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P0,
        )

        _page_high_sev_if_needed(incident)

        mock_pd_cls.assert_not_called()

    def test_skips_when_no_high_sev_policy(self, settings):
        settings.PAGERDUTY = {
            "API_TOKEN": "test-token",
            "ESCALATION_POLICIES": {},
        }

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P0,
        )

        _page_high_sev_if_needed(incident)

    def test_skips_when_no_integration_key(self, settings):
        settings.PAGERDUTY = {
            "API_TOKEN": "test-token",
            "ESCALATION_POLICIES": {
                "HIGH_SEV": {"id": "P17I207", "integration_key": None},
            },
        }

        incident = Incident.objects.create(
            title="Test",
            severity=IncidentSeverity.P0,
        )

        _page_high_sev_if_needed(incident)


@pytest.mark.django_db
class TestOnIncidentCreatedPagerDuty:
    @patch("firetower.incidents.hooks._page_high_sev_if_needed")
    @patch("firetower.incidents.hooks._slack_service")
    def test_pages_high_sev_on_p0_creation(self, mock_slack, mock_page):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Major outage",
            severity=IncidentSeverity.P0,
        )

        on_incident_created(incident)

        mock_page.assert_called_once_with(incident)

    @patch("firetower.incidents.hooks._page_high_sev_if_needed")
    @patch("firetower.incidents.hooks._slack_service")
    def test_on_incident_created_calls_page_high_sev_if_needed(
        self, mock_slack, mock_page
    ):
        mock_slack.create_channel.return_value = "C99999"
        mock_slack.build_channel_url.return_value = "https://slack.com/archives/C99999"

        incident = Incident.objects.create(
            title="Minor issue",
            severity=IncidentSeverity.P3,
        )

        on_incident_created(incident)

        mock_page.assert_called_once_with(incident)


@pytest.mark.django_db
class TestOnSeverityChangedPagerDuty:
    @patch("firetower.incidents.hooks._page_high_sev_if_needed")
    @patch("firetower.incidents.hooks._slack_service")
    def test_pages_high_sev_on_upgrade_to_p0(self, mock_slack, mock_page):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Escalating issue",
            severity=IncidentSeverity.P0,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_severity_changed(incident, IncidentSeverity.P2)

        mock_page.assert_called_once_with(incident)

    @patch("firetower.incidents.hooks._page_high_sev_if_needed")
    @patch("firetower.incidents.hooks._slack_service")
    def test_pages_high_sev_on_upgrade_to_p1(self, mock_slack, mock_page):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Escalating issue",
            severity=IncidentSeverity.P1,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_severity_changed(incident, IncidentSeverity.P3)

        mock_page.assert_called_once_with(incident)

    @patch("firetower.incidents.hooks._page_high_sev_if_needed")
    @patch("firetower.incidents.hooks._slack_service")
    def test_does_not_page_on_p1_to_p0(self, mock_slack, mock_page):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Already paged",
            severity=IncidentSeverity.P0,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_severity_changed(incident, IncidentSeverity.P1)

        mock_page.assert_not_called()

    @patch("firetower.incidents.hooks._page_high_sev_if_needed")
    @patch("firetower.incidents.hooks._slack_service")
    def test_does_not_page_on_downgrade(self, mock_slack, mock_page):
        mock_slack.parse_channel_id_from_url.return_value = "C12345"

        incident = Incident.objects.create(
            title="Downgraded",
            severity=IncidentSeverity.P3,
        )
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://slack.com/archives/C12345",
        )

        on_severity_changed(incident, IncidentSeverity.P1)

        mock_page.assert_not_called()
