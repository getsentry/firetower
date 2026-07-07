from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import User

from firetower.incidents.allocation import PLACEHOLDER_TITLE
from firetower.incidents.models import (
    ExternalLink,
    ExternalLinkType,
    Incident,
    IncidentCounter,
    IncidentStatus,
    PendingIncident,
)
from firetower.incidents.tasks.recovery import (
    _finalize_pending_incident,
    _repair_missing_parents,
    ensure_linear_parent_for_incident,
    sweep_incident_recovery,
)
from firetower.integrations.services.linear import LinearError


def _identifier(n: int) -> str:
    return f"{django_settings.PROJECT_KEY}-{n}"


def _placeholder(n: int, *, title: str = PLACEHOLDER_TITLE) -> dict:
    return {
        "id": f"uuid-{n}",
        "identifier": _identifier(n),
        "title": title,
        "url": f"https://linear.app/issue/{_identifier(n)}",
    }


def _set_counter(next_id: int) -> None:
    IncidentCounter.objects.update_or_create(pk=1, defaults={"next_id": next_id})


def _make_user(email: str = "reporter@example.com") -> User:
    return User.objects.create(username=email, email=email)


def _make_pending(channel_id: str = "C_TMP", severity: str = "P2") -> PendingIncident:
    return PendingIncident.objects.create(
        slack_channel_id=channel_id,
        title="Something broke",
        severity=severity,
        description="desc",
        impact_summary="impact",
        is_private=False,
        captain_slack_id="U_CAP",
        reporter_slack_id="U_REP",
    )


@pytest.fixture
def adopt_enabled(settings):
    settings.LINEAR = {
        "SYNC_IDENTIFIERS": True,
        "INCIDENT_ADOPT_ON_CREATE": True,
        "TEAM_ID": "team-1",
        "PROJECT_ID": "proj-1",
    }
    return settings


def _patch_alloc_linear(linear: MagicMock):
    return patch(
        "firetower.incidents.allocation.LinearService.for_allocation",
        return_value=linear,
    )


@pytest.mark.django_db
class TestFinalizePendingIncident:
    def test_finalizes_when_linear_recovers(self, adopt_enabled):
        _set_counter(2400)
        pending = _make_pending()
        user = _make_user()

        linear = MagicMock()
        linear.get_issue.side_effect = lambda ident, *, raise_on_error=False: (
            _placeholder(2400) if ident == _identifier(2400) else None
        )

        client = MagicMock()
        with (
            _patch_alloc_linear(linear),
            patch(
                "firetower.incidents.tasks.recovery.get_or_create_user_from_slack_id",
                return_value=user,
            ),
            patch("firetower.incidents.tasks.recovery._slack_service") as slack,
            patch(
                "firetower.incidents.tasks.recovery.populate_linear_parent"
            ) as populate,
            patch(
                "firetower.slack_app.handlers.backfill_incident._setup_channel_for_incident"
            ) as setup,
        ):
            slack.build_channel_url.return_value = (
                "https://sentry.slack.com/archives/C_TMP"
            )
            _finalize_pending_incident(pending, client)

        incident = Incident.objects.get(pk=2400)
        assert incident.linear_parent_issue_id == "uuid-2400"
        populate.assert_called_once()
        setup.assert_called_once()
        assert not PendingIncident.objects.filter(slack_channel_id="C_TMP").exists()

    def test_leaves_row_when_linear_still_down(self, adopt_enabled):
        _set_counter(2400)
        pending = _make_pending()
        user = _make_user()

        linear = MagicMock()
        # get_issue raises the transport error signal -> allocator raises
        # LinearUnavailable before any incident is created.
        linear.get_issue.side_effect = LinearError("down")

        client = MagicMock()
        with (
            _patch_alloc_linear(linear),
            patch(
                "firetower.incidents.tasks.recovery.get_or_create_user_from_slack_id",
                return_value=user,
            ),
            patch("firetower.incidents.tasks.recovery._slack_service") as slack,
        ):
            slack.build_channel_url.return_value = (
                "https://sentry.slack.com/archives/C_TMP"
            )
            _finalize_pending_incident(pending, client)

        assert PendingIncident.objects.filter(slack_channel_id="C_TMP").exists()
        assert not Incident.objects.exists()

    def test_idempotent_when_channel_already_linked(self, adopt_enabled):
        pending = _make_pending()
        incident = Incident.objects.create(id=2401, title="x", severity="P2")
        ExternalLink.objects.create(
            incident=incident,
            type=ExternalLinkType.SLACK,
            url="https://sentry.slack.com/archives/C_TMP",
        )

        client = MagicMock()
        with patch(
            "firetower.incidents.tasks.recovery.get_or_create_user_from_slack_id"
        ) as get_user:
            _finalize_pending_incident(pending, client)
            get_user.assert_not_called()

        assert not PendingIncident.objects.filter(slack_channel_id="C_TMP").exists()
        assert Incident.objects.count() == 1

    def test_leaves_row_when_reporter_unresolvable(self, adopt_enabled):
        pending = _make_pending()
        client = MagicMock()
        with patch(
            "firetower.incidents.tasks.recovery.get_or_create_user_from_slack_id",
            return_value=None,
        ):
            _finalize_pending_incident(pending, client)

        assert PendingIncident.objects.filter(slack_channel_id="C_TMP").exists()
        assert not Incident.objects.exists()


@pytest.mark.django_db
class TestEnsureLinearParent:
    def _incident(self, inc_id: int = 2500) -> Incident:
        return Incident.objects.create(id=inc_id, title="t", severity="P1")

    def test_no_op_when_parent_already_set(self, adopt_enabled):
        incident = self._incident()
        incident.linear_parent_issue_id = "already"
        incident.save(update_fields=["linear_parent_issue_id"])

        with patch(
            "firetower.incidents.tasks.recovery._get_linear_service"
        ) as get_linear:
            ensure_linear_parent_for_incident(incident)
            get_linear.assert_not_called()

    def test_adopts_matching_placeholder(self, adopt_enabled):
        incident = self._incident(2500)
        linear = MagicMock()
        linear.get_issue.return_value = _placeholder(2500)

        with (
            patch(
                "firetower.incidents.tasks.recovery._get_linear_service",
                return_value=linear,
            ),
            patch(
                "firetower.incidents.tasks.recovery._get_channel_id",
                return_value=None,
            ),
            patch(
                "firetower.incidents.tasks.recovery.populate_linear_parent"
            ) as populate,
        ):
            ensure_linear_parent_for_incident(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id == "uuid-2500"
        populate.assert_called_once()

    def test_skips_non_placeholder(self, adopt_enabled):
        incident = self._incident(2500)
        linear = MagicMock()
        linear.get_issue.return_value = _placeholder(2500, title="Real issue")

        with (
            patch(
                "firetower.incidents.tasks.recovery._get_linear_service",
                return_value=linear,
            ),
            patch(
                "firetower.incidents.tasks.recovery._get_channel_id",
                return_value=None,
            ),
            patch(
                "firetower.incidents.tasks.recovery.populate_linear_parent"
            ) as populate,
        ):
            ensure_linear_parent_for_incident(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id is None
        populate.assert_not_called()

    def test_skips_aliased_identifier(self, adopt_enabled):
        incident = self._incident(2500)
        linear = MagicMock()
        aliased = _placeholder(2500)
        aliased["identifier"] = "PRODENG-1"
        linear.get_issue.return_value = aliased

        with (
            patch(
                "firetower.incidents.tasks.recovery._get_linear_service",
                return_value=linear,
            ),
            patch(
                "firetower.incidents.tasks.recovery._get_channel_id",
                return_value=None,
            ),
            patch(
                "firetower.incidents.tasks.recovery.populate_linear_parent"
            ) as populate,
        ):
            ensure_linear_parent_for_incident(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id is None
        populate.assert_not_called()

    def test_skips_placeholder_already_adopted(self, adopt_enabled):
        incident = self._incident(2500)
        other = Incident.objects.create(id=2499, title="other", severity="P1")
        other.linear_parent_issue_id = "uuid-2500"
        other.save(update_fields=["linear_parent_issue_id"])

        linear = MagicMock()
        linear.get_issue.return_value = _placeholder(2500)

        with (
            patch(
                "firetower.incidents.tasks.recovery._get_linear_service",
                return_value=linear,
            ),
            patch(
                "firetower.incidents.tasks.recovery._get_channel_id",
                return_value=None,
            ),
            patch(
                "firetower.incidents.tasks.recovery.populate_linear_parent"
            ) as populate,
        ):
            ensure_linear_parent_for_incident(incident)

        incident.refresh_from_db()
        assert incident.linear_parent_issue_id is None
        populate.assert_not_called()

    def test_creates_fresh_issue_when_not_syncing(self, settings):
        settings.LINEAR = {"TEAM_ID": "team-1", "SYNC_IDENTIFIERS": False}
        incident = self._incident(2500)

        with patch(
            "firetower.incidents.tasks.recovery.create_linear_parent_issue"
        ) as create:
            ensure_linear_parent_for_incident(incident)
            create.assert_called_once()


@pytest.mark.django_db
class TestRepairMissingParents:
    def test_repairs_recent_incident_without_parent(self, adopt_enabled):
        incident = Incident.objects.create(id=2600, title="t", severity="P1")

        with patch(
            "firetower.incidents.tasks.recovery.ensure_linear_parent_for_incident"
        ) as ensure:
            _repair_missing_parents()
            ensure.assert_called_once()
            assert ensure.call_args[0][0].id == incident.id

    def test_excludes_canceled(self, adopt_enabled):
        Incident.objects.create(
            id=2601, title="t", severity="P1", status=IncidentStatus.CANCELED
        )

        with patch(
            "firetower.incidents.tasks.recovery.ensure_linear_parent_for_incident"
        ) as ensure:
            _repair_missing_parents()
            ensure.assert_not_called()

    def test_skips_when_linear_unset(self, settings):
        settings.LINEAR = None
        Incident.objects.create(id=2602, title="t", severity="P1")

        with patch(
            "firetower.incidents.tasks.recovery.ensure_linear_parent_for_incident"
        ) as ensure:
            _repair_missing_parents()
            ensure.assert_not_called()


@pytest.mark.django_db
class TestSweep:
    def test_runs_finalize_and_repair(self, adopt_enabled):
        _make_pending()

        with (
            patch("firetower.slack_app.bolt.get_bolt_app") as get_bolt,
            patch(
                "firetower.incidents.tasks.recovery._finalize_pending_incident"
            ) as finalize,
            patch(
                "firetower.incidents.tasks.recovery._repair_missing_parents"
            ) as repair,
        ):
            get_bolt.return_value.client = MagicMock()
            sweep_incident_recovery()

        finalize.assert_called_once()
        repair.assert_called_once()

    def test_repairs_even_without_slack_client(self, adopt_enabled):
        _make_pending()

        with (
            patch(
                "firetower.slack_app.bolt.get_bolt_app",
                side_effect=RuntimeError("no slack"),
            ),
            patch(
                "firetower.incidents.tasks.recovery._finalize_pending_incident"
            ) as finalize,
            patch(
                "firetower.incidents.tasks.recovery._repair_missing_parents"
            ) as repair,
        ):
            sweep_incident_recovery()

        finalize.assert_not_called()
        repair.assert_called_once()
