from datetime import UTC, datetime, timedelta
from importlib import import_module
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser, User
from django_q.models import Schedule
from rest_framework.test import APIClient

from firetower.incidents.action_item_reporting import build_action_item_dashboard
from firetower.incidents.models import ActionItem, Incident, filter_visible_to_user
from firetower.incidents.services import (
    ActionItemsSyncStats,
    sync_action_items_from_linear,
)
from firetower.incidents.tasks.action_items import refresh_action_item_dashboard
from firetower.integrations.services.linear import ISSUE_FIELDS, LinearService

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
URL = "/api/ui/action-items/"
ENG_TEAM_ID = "11111111-1111-4111-8111-111111111111"
INFRA_TEAM_ID = "22222222-2222-4222-8222-222222222222"
SECRET_TEAM_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def dashboard(settings, monkeypatch, _disable_linear):
    settings.LINEAR = {
        "ACTION_ITEM_SLO_DAYS_HIGH_PRIORITY": 14,
        "ACTION_ITEM_SLO_DAYS_MEDIUM_PRIORITY": 30,
    }
    monkeypatch.setattr("firetower.incidents.views.timezone.now", lambda: NOW)
    user = User.objects.create_user(
        username="reader", first_name="Test", last_name="Owner"
    )
    client = APIClient()
    client.force_authenticate(user)
    incident = Incident.objects.create(
        title="Database outage",
        severity="P1",
        status="Done",
        linear_parent_issue_id="parent",
        action_items_last_synced_at=NOW,
    )
    return client, user, incident


def make_item(incident, **kwargs):
    number = ActionItem.objects.count() + 1
    defaults = {
        "linear_issue_id": f"issue-{number}",
        "linear_identifier": f"ENG-{number}",
        "title": f"Follow-up {number}",
        "url": f"https://linear.app/issue/ENG-{number}",
        "status": "Todo",
        "priority": 4,
        "created_at": NOW - timedelta(days=1),
        "linear_updated_at": NOW,
        "linear_team_id": ENG_TEAM_ID,
        "linear_team_key": "ENG",
        "linear_team_name": "Engineering",
    }
    defaults.update(kwargs)
    return ActionItem.objects.create(incident=incident, **defaults)


@pytest.mark.django_db
class TestActionItemDashboard:
    def test_summary_counts_only_open_risks_and_real_completions(self, dashboard):
        client, user, incident = dashboard
        make_item(
            incident,
            assignee=user,
            priority=1,
            created_at=NOW - timedelta(days=20),
            linear_updated_at=NOW - timedelta(days=15),
        )
        make_item(
            incident, assignee=user, priority=2, created_at=NOW - timedelta(days=13)
        )
        make_item(
            incident,
            assignee=user,
            created_at=NOW - timedelta(days=31),
            linear_updated_at=NOW - timedelta(days=14),
        )
        make_item(incident)
        make_item(incident, assignee=user, priority=0)
        make_item(incident, assignee=user, priority=3, status="In Progress")
        make_item(
            incident,
            status="Done",
            priority=2,
            created_at=NOW - timedelta(days=40),
            completed_at=NOW - timedelta(days=5),
        )
        make_item(
            incident,
            status="Done",
            priority=2,
            created_at=NOW - timedelta(days=8),
            completed_at=NOW - timedelta(days=2),
        )
        make_item(incident, status="Done", completed_at=None)
        make_item(
            incident,
            status="Done",
            created_at=NOW - timedelta(days=70),
            completed_at=NOW - timedelta(days=40),
        )
        make_item(
            incident,
            status="Canceled",
            priority=1,
            created_at=NOW - timedelta(days=100),
        )

        response = client.get(URL)
        assert response.status_code == 200
        data = response.data
        summary = data["summary"]
        assert summary["open"] == 6
        assert summary["todo"] == 5
        assert summary["in_progress"] == 1
        assert summary["overdue"] == 1
        assert summary["due_soon"] == 1
        assert summary["stalled"] == 2
        assert summary["unassigned"] == 1
        assert summary["no_priority"] == 1
        assert summary["attention"] == 5
        assert summary["completed_30d"] == 2
        assert summary["median_completion_days"] == 20.5
        assert summary["on_time_percent"] == 50
        assert summary["on_time_sample"] == 2
        assert summary["canceled"] == 1
        assert summary["unknown_completion"] == 1
        assert data["queue"]["count"] == 5
        assert data["queue"]["results"][0]["flags"] == ["overdue", "stalled"]
        assert sum(bucket["count"] for bucket in data["aging"]) == 6
        assert sum(week["completed"] for week in data["weeks"]) == 3
        assert sum(team["open"] for team in data["teams"]) == 6
        assert data["teams"][0]["completed"] == 4
        assert data["teams"][0]["canceled"] == 1
        assert data["teams"][0]["total"] == 11
        assert data["teams"][0]["completion_rate"] == 40

    def test_deadline_and_idle_boundaries(self, dashboard):
        client, user, incident = dashboard
        overdue = make_item(
            incident,
            assignee=user,
            priority=2,
            created_at=NOW - timedelta(days=14),
            linear_updated_at=NOW - timedelta(days=14),
        )
        soon = make_item(
            incident, assignee=user, priority=3, created_at=NOW - timedelta(days=27)
        )
        make_item(
            incident, assignee=user, priority=3, created_at=NOW - timedelta(days=26)
        )
        data = client.get(URL).data
        assert data["summary"]["overdue"] == 1
        assert data["summary"]["due_soon"] == 1
        assert data["summary"]["stalled"] == 1
        assert [row["id"] for row in data["queue"]["results"]] == [overdue.id, soon.id]

    def test_explicit_due_date_changes_and_removal_update_risk(self, dashboard):
        client, user, incident = dashboard
        item = make_item(
            incident,
            assignee=user,
            priority=4,
            linear_due_date=NOW.date() - timedelta(days=1),
        )
        data = client.get(URL, {"view": "open"}).data
        assert data["summary"]["overdue"] == 1
        assert data["queue"]["results"][0]["deadline_source"] == "linear_due_date"
        assert data["queue"]["results"][0]["due_date"] == "2026-11-16"

        item.linear_due_date = NOW.date() + timedelta(days=2)
        item.save(update_fields=["linear_due_date"])
        data = client.get(URL, {"view": "open"}).data
        assert data["summary"]["overdue"] == 0
        assert data["summary"]["due_soon"] == 1

        item.linear_due_date = None
        item.save(update_fields=["linear_due_date"])
        data = client.get(URL, {"view": "open"}).data
        assert data["summary"]["overdue"] == 0
        assert data["summary"]["due_soon"] == 0
        assert data["queue"]["results"][0]["slo_deadline"] is None
        assert data["queue"]["results"][0]["deadline_source"] is None

    def test_linear_sla_changes_override_the_priority_target(self, dashboard):
        client, user, incident = dashboard
        item = make_item(
            incident,
            assignee=user,
            priority=2,
            created_at=NOW - timedelta(days=20),
            linear_sla_breaches_at=NOW + timedelta(days=5),
        )
        data = client.get(URL, {"view": "open"}).data
        assert data["summary"]["overdue"] == 0
        assert data["queue"]["results"][0]["deadline_source"] == "linear_sla"

        item.linear_sla_breaches_at = NOW - timedelta(days=1)
        item.save(update_fields=["linear_sla_breaches_at"])
        assert client.get(URL).data["summary"]["overdue"] == 1

        item.linear_sla_breaches_at = None
        item.save(update_fields=["linear_sla_breaches_at"])
        data = client.get(URL).data
        assert data["summary"]["overdue"] == 1
        assert data["queue"]["results"][0]["deadline_source"] == "priority_slo"

    def test_on_time_metrics_use_current_linear_deadlines(self, dashboard):
        client, _, incident = dashboard
        done = {
            "status": "Done",
            "created_at": NOW - timedelta(days=10),
            "completed_at": NOW - timedelta(days=1),
        }
        dated = make_item(incident, priority=0, linear_due_date=NOW.date(), **done)
        make_item(
            incident, priority=2, linear_sla_breaches_at=NOW - timedelta(days=5), **done
        )
        make_item(
            incident,
            priority=2,
            linear_due_date=NOW.date(),
            linear_sla_breaches_at=NOW - timedelta(days=5),
            **done,
        )
        make_item(incident, priority=4, **done)
        data = client.get(URL).data
        assert data["summary"]["completed_30d"] == 4
        assert data["summary"]["on_time_sample"] == 3
        assert data["summary"]["on_time_percent"] == 66.7
        dated.linear_due_date = NOW.date() - timedelta(days=5)
        dated.save(update_fields=["linear_due_date"])
        assert client.get(URL).data["summary"]["on_time_percent"] == 33.3

    def test_unknown_activity_is_not_fabricated_from_sync_time(self, dashboard):
        client, user, incident = dashboard
        make_item(
            incident,
            assignee=user,
            created_at=NOW - timedelta(days=200),
            linear_updated_at=None,
        )
        data = client.get(URL, {"view": "open"}).data
        assert data["summary"]["stalled"] == 0
        assert data["summary"]["unknown_activity"] == 1
        assert data["queue"]["results"][0]["idle_days"] is None
        assert data["aging"][-1]["count"] == 1

    @pytest.mark.parametrize(
        "role",
        [
            "outsider",
            "captain",
            "reporter",
            "participant",
            "superuser",
            "service_account",
        ],
    )
    def test_visibility_applies_to_every_part_of_report(self, dashboard, role):
        client, user, public = dashboard
        secret_owner = User.objects.create_user(username="hidden-owner")
        private = Incident.objects.create(
            title="Secret incident",
            severity="P0",
            is_private=True,
            linear_parent_issue_id="secret",
        )
        if role in ("captain", "reporter"):
            setattr(private, role, user)
            private.save()
        if role == "participant":
            private.participants.add(user, secret_owner)
        if role == "superuser":
            user.is_superuser = True
            user.save()
        if role == "service_account":
            user.email = "dashboard@project.iam.gserviceaccount.com"
            user.save()
            private.captain = user
            private.save()
        make_item(public, title="Public follow-up")
        make_item(
            private,
            assignee=secret_owner,
            priority=1,
            title="Secret follow-up",
            linear_team_id=SECRET_TEAM_ID,
            linear_team_key="SECRET",
            linear_team_name="Private ownership team",
            created_at=NOW - timedelta(days=20),
        )
        data = client.get(URL).data
        visible = role in ("captain", "reporter", "participant")
        assert data["summary"]["open"] == (2 if visible else 1)
        assert data["summary"]["overdue"] == (1 if visible else 0)
        assert data["freshness"]["linked_incidents"] == (2 if visible else 1)
        assert ("Secret follow-up" in str(data)) is visible
        assert "hidden-owner" not in str(data)
        assert ("Private ownership team" in str(data)) is visible
        assert sum(team["open"] for team in data["teams"]) == (2 if visible else 1)
        assert sum(bucket["count"] for bucket in data["aging"]) == (2 if visible else 1)

    def test_canceled_incidents_excluded_but_closed_incidents_included(self, dashboard):
        client, _, done = dashboard
        canceled = Incident.objects.create(
            title="Canceled", status="Canceled", severity="P0"
        )
        make_item(done)
        make_item(canceled)
        assert client.get(URL).data["summary"]["open"] == 1

    def test_severity_scopes_dashboard_but_queue_filters_do_not(self, dashboard):
        client, user, p1 = dashboard
        p2 = Incident.objects.create(title="Minor", severity="P2")
        first = make_item(
            p1,
            assignee=user,
            title="Increase connection pool",
            priority=2,
            created_at=NOW - timedelta(days=15),
        )
        make_item(
            p1,
            linear_team_id=INFRA_TEAM_ID,
            linear_team_key="INFRA",
            linear_team_name="Infrastructure",
        )
        make_item(p2, priority=2, created_at=NOW - timedelta(days=15))
        data = client.get(
            URL,
            {
                "severity": "P1",
                "view": "overdue",
                "team": ENG_TEAM_ID,
                "q": "CONNECTION",
            },
        ).data
        assert data["summary"]["open"] == 2
        assert data["summary"]["overdue"] == 1
        assert data["queue"]["count"] == 1
        assert data["queue"]["results"][0]["id"] == first.id
        infrastructure = client.get(URL, {"severity": "P1", "team": INFRA_TEAM_ID}).data
        assert infrastructure["queue"]["count"] == 1
        assert client.get(URL, {"q": "infrastructure"}).data["queue"]["count"] == 1
        assert (
            client.get(URL, {"q": p1.incident_number.lower()}).data["queue"]["count"]
            == 2
        )
        assert client.get(URL, {"q": "not-found"}).data["summary"]["open"] == 3

    @pytest.mark.parametrize(
        "view",
        [
            "attention",
            "open",
            "overdue",
            "due_soon",
            "stalled",
            "unassigned",
            "no_priority",
        ],
    )
    def test_queue_views_match_their_summary_count(self, dashboard, view):
        client, user, incident = dashboard
        make_item(
            incident,
            assignee=user,
            priority=1,
            created_at=NOW - timedelta(days=20),
            linear_updated_at=NOW - timedelta(days=15),
        )
        make_item(incident, priority=0)
        make_item(incident, priority=2, created_at=NOW - timedelta(days=13))
        make_item(incident, assignee=user)
        data = client.get(URL, {"view": view}).data
        assert data["queue"]["count"] == data["summary"][view]

    def test_teams_group_work_without_individual_identity(self, dashboard):
        client, user, incident = dashboard
        other = User.objects.create_user(
            username="another-engineer", first_name="Another", last_name="Engineer"
        )
        first = make_item(incident, assignee=user)
        make_item(incident, assignee=other)
        make_item(
            incident,
            assignee=user,
            linear_team_id=INFRA_TEAM_ID,
            linear_team_key="INFRA",
            linear_team_name="Infrastructure",
        )
        data = client.get(URL, {"view": "open"}).data
        assert [(team["id"], team["open"]) for team in data["teams"]] == [
            (ENG_TEAM_ID, 2),
            (INFRA_TEAM_ID, 1),
        ]
        assert data["summary"]["unknown_team"] == 0
        assert "owners" not in data
        assert user.get_full_name() not in str(data)
        assert other.get_full_name() not in str(data)
        for row in data["queue"]["results"]:
            assert (
                not {"assignee_name", "assignee_avatar_url", "assignee_id"} & row.keys()
            )
        assert (
            client.get(URL, {"view": "open", "q": other.get_full_name()}).data["queue"][
                "count"
            ]
            == 0
        )
        ActionItem.objects.filter(pk=first.pk).update(assignee=other)
        assert (
            client.get(URL, {"view": "open", "team": ENG_TEAM_ID}).data["queue"][
                "count"
            ]
            == 2
        )

    def test_missing_team_metadata_is_explicit_and_filterable(self, dashboard):
        client, _, incident = dashboard
        make_item(incident, linear_team_id="", linear_team_key="", linear_team_name="")
        make_item(incident)
        data = client.get(URL, {"team": "unknown"}).data
        assert data["summary"]["unknown_team"] == 1
        assert data["summary"]["open"] == 2
        assert data["queue"]["count"] == 1
        assert (
            next(team for team in data["teams"] if team["id"] == "unknown")["name"]
            == "Team not synced"
        )

    def test_team_identity_comes_from_linear_not_identifier_prefix(self, dashboard):
        client, _, incident = dashboard
        item = make_item(
            incident,
            linear_identifier="ENG-123",
            linear_team_id=INFRA_TEAM_ID,
            linear_team_key="INFRA",
            linear_team_name="Infrastructure",
        )
        data = client.get(URL, {"team": INFRA_TEAM_ID}).data
        assert data["teams"][0]["id"] == INFRA_TEAM_ID
        assert data["teams"][0]["name"] == "Infrastructure"
        assert data["queue"]["results"][0]["id"] == item.id

    def test_team_progress_includes_completed_only_teams_and_excludes_canceled_from_rate(
        self, dashboard
    ):
        client, _, incident = dashboard
        for _ in range(4):
            make_item(incident, status="Done")
        for _ in range(2):
            make_item(incident)
        make_item(incident, status="Canceled")
        for _ in range(2):
            make_item(
                incident,
                status="Done",
                linear_team_id=INFRA_TEAM_ID,
                linear_team_key="INFRA",
                linear_team_name="Infrastructure",
            )
        make_item(
            incident,
            status="Canceled",
            linear_team_id=SECRET_TEAM_ID,
            linear_team_key="OLD",
            linear_team_name="Retired team",
        )

        data = client.get(URL).data
        teams = {team["id"]: team for team in data["teams"]}
        assert teams[ENG_TEAM_ID]["completed"] == 4
        assert teams[ENG_TEAM_ID]["open"] == 2
        assert teams[ENG_TEAM_ID]["canceled"] == 1
        assert teams[ENG_TEAM_ID]["total"] == 7
        assert teams[ENG_TEAM_ID]["completion_rate"] == 66.7
        assert teams[INFRA_TEAM_ID]["completed"] == 2
        assert teams[INFRA_TEAM_ID]["open"] == 0
        assert teams[INFRA_TEAM_ID]["total"] == 2
        assert teams[INFRA_TEAM_ID]["completion_rate"] == 100
        assert teams[SECRET_TEAM_ID]["total"] == 1
        assert teams[SECRET_TEAM_ID]["canceled"] == 1
        assert teams[SECRET_TEAM_ID]["completion_rate"] is None
        assert sum(team["total"] for team in teams.values()) == 10

    def test_positive_team_metrics_respect_visibility_and_severity_not_queue_filters(
        self, dashboard
    ):
        client, _, incident = dashboard
        make_item(incident, status="Done")
        make_item(incident, status="Done")
        minor = Incident.objects.create(title="Minor incident", severity="P2")
        make_item(
            minor,
            status="Done",
            linear_team_id=INFRA_TEAM_ID,
            linear_team_key="INFRA",
            linear_team_name="Infrastructure",
        )
        hidden = Incident.objects.create(
            title="Secret incident", severity="P1", is_private=True
        )
        make_item(
            hidden,
            status="Done",
            linear_team_id=SECRET_TEAM_ID,
            linear_team_key="SECRET",
            linear_team_name="Private team",
        )
        data = client.get(
            URL, {"severity": "P1", "view": "overdue", "q": "nothing-matches"}
        ).data
        assert data["queue"]["count"] == 0
        assert len(data["teams"]) == 1
        assert data["teams"][0]["id"] == ENG_TEAM_ID
        assert data["teams"][0]["completed"] == 2
        assert data["teams"][0]["total"] == 2
        assert data["teams"][0]["completion_rate"] == 100
        assert "Private team" not in str(data)
        assert "Infrastructure" not in str(data)

    def test_pagination_is_stable_and_bounds_oversized_pages(self, dashboard):
        client, _, incident = dashboard
        for _ in range(22):
            make_item(incident)
        first = client.get(URL).data["queue"]
        second = client.get(URL, {"page": 2}).data["queue"]
        last = client.get(URL, {"page": 999}).data["queue"]
        assert first["count"] == second["count"] == 22
        assert first["pages"] == 3
        assert len(first["results"]) == len(second["results"]) == 10
        assert not {row["id"] for row in first["results"]} & {
            row["id"] for row in second["results"]
        }
        assert len(last["results"]) == 2
        assert last["page"] == 3

    @pytest.mark.parametrize(
        "params",
        [
            {"severity": "P9"},
            {"view": "wrong"},
            {"page": 0},
            {"page": -1},
            {"page": "bad"},
            {"page": 100001},
            {"q": "x" * 201},
            {"team": "bad"},
        ],
    )
    def test_invalid_parameters(self, dashboard, params):
        client, _, _ = dashboard
        assert client.get(URL, params).status_code == 400

    def test_empty_report_has_no_misleading_percentages(self, dashboard):
        client, _, _ = dashboard
        data = client.get(URL).data
        assert data["summary"]["open"] == 0
        assert data["summary"]["median_completion_days"] is None
        assert data["summary"]["on_time_percent"] is None
        assert data["queue"] == {"count": 0, "page": 1, "pages": 1, "results": []}
        assert len(data["weeks"]) == 8

    def test_no_target_is_not_on_time_and_impossible_dates_are_excluded(
        self, dashboard
    ):
        client, _, incident = dashboard
        make_item(
            incident,
            status="Done",
            created_at=NOW - timedelta(days=5),
            completed_at=NOW,
        )
        make_item(
            incident, status="Done", priority=1, completed_at=NOW + timedelta(days=1)
        )
        make_item(
            incident,
            status="Done",
            priority=1,
            created_at=NOW,
            completed_at=NOW - timedelta(days=1),
        )
        data = client.get(URL).data
        assert data["summary"]["completed_30d"] == 1
        assert data["summary"]["on_time_percent"] is None
        assert data["summary"]["on_time_sample"] == 0
        assert sum(week["completed"] for week in data["weeks"]) == 1

    def test_freshness_reports_missing_and_stale_syncs(self, dashboard):
        client, _, _ = dashboard
        Incident.objects.create(
            title="Old",
            severity="P1",
            linear_parent_issue_id="old",
            action_items_last_synced_at=NOW - timedelta(days=2),
        )
        Incident.objects.create(
            title="Never synced", severity="P1", linear_parent_issue_id="never"
        )
        Incident.objects.create(title="No Linear parent", severity="P1")
        data = client.get(URL).data
        assert data["freshness"] == {
            "linked_incidents": 3,
            "unlinked_incidents": 1,
            "unsynced_incidents": 1,
            "stale_incidents": 1,
            "oldest_sync_at": (NOW - timedelta(days=2)).isoformat(),
        }

    def test_anonymous_access_denied(self):
        client = APIClient()
        client.force_authenticate(AnonymousUser())
        assert client.get(URL).status_code in (401, 403)

    def test_get_is_read_only_and_has_constant_query_count(
        self, dashboard, django_assert_num_queries
    ):
        client, user, incident = dashboard
        for _ in range(20):
            make_item(incident, assignee=user)
        with django_assert_num_queries(2):
            build_action_item_dashboard(
                filter_visible_to_user(Incident.objects.all(), user), now=NOW
            )
        with patch("firetower.incidents.views.sync_action_items_from_linear") as sync:
            assert client.get(URL).status_code == 200
            sync.assert_not_called()


@pytest.mark.django_db
class TestDashboardSync:
    def test_sync_persists_linear_activity_and_clears_completion_on_reopen(
        self, dashboard
    ):
        _, _, incident = dashboard
        raw = {
            "id": "issue",
            "identifier": "ENG-1",
            "title": "Fix",
            "url": "https://linear.app/issue/ENG-1",
            "createdAt": (NOW - timedelta(days=20)).isoformat(),
            "updatedAt": (NOW - timedelta(days=5)).isoformat(),
            "completedAt": (NOW - timedelta(days=5)).isoformat(),
            "state": {"type": "completed"},
            "team": {"id": ENG_TEAM_ID, "key": "ENG", "name": "Engineering"},
        }
        service = LinearService.__new__(LinearService)
        parsed = service._parse_issue(raw)
        assert "updatedAt" in ISSUE_FIELDS and "completedAt" in ISSUE_FIELDS
        with patch("firetower.incidents.services._get_linear_service") as get_service:
            get_service.return_value.get_child_issues.return_value = [parsed]
            sync_action_items_from_linear(incident, force=True)
            item = incident.action_items.get()
            assert item.linear_updated_at == NOW - timedelta(days=5)
            assert item.completed_at == NOW - timedelta(days=5)
            assert item.updated_at == NOW
            assert (
                item.linear_team_id,
                item.linear_team_key,
                item.linear_team_name,
            ) == (ENG_TEAM_ID, "ENG", "Engineering")
            raw.update(
                state={"type": "started"},
                completedAt=None,
                updatedAt=NOW.isoformat(),
                team={"id": INFRA_TEAM_ID, "key": "INFRA", "name": "Infrastructure"},
            )
            get_service.return_value.get_child_issues.return_value = [
                service._parse_issue(raw)
            ]
            sync_action_items_from_linear(incident, force=True)
            item.refresh_from_db()
            assert item.status == "In Progress"
            assert item.completed_at is None
            assert item.linear_updated_at == NOW
            assert (
                item.linear_team_id,
                item.linear_team_key,
                item.linear_team_name,
            ) == (INFRA_TEAM_ID, "INFRA", "Infrastructure")

    def test_sync_copies_edited_and_cleared_linear_deadlines(self, dashboard):
        _, _, incident = dashboard
        raw = {
            "id": "dated-issue",
            "identifier": "ENG-99",
            "title": "Dated follow-up",
            "url": "https://linear.app/issue/ENG-99",
            "priority": 2,
            "createdAt": (NOW - timedelta(days=20)).isoformat(),
            "state": {"type": "unstarted"},
            "dueDate": "2026-11-16",
            "slaBreachesAt": (NOW + timedelta(days=14)).isoformat(),
        }
        service = LinearService.__new__(LinearService)
        assert "dueDate" in ISSUE_FIELDS
        with patch("firetower.incidents.services._get_linear_service") as get_service:

            def sync():
                get_service.return_value.get_child_issues.return_value = [
                    service._parse_issue(raw)
                ]
                sync_action_items_from_linear(incident, force=True)
                return incident.action_items.get()

            item = sync()
            assert item.linear_due_date == NOW.date() - timedelta(days=1)
            assert item.linear_sla_breaches_at == NOW + timedelta(days=14)

            raw.update(
                dueDate="2026-11-20",
                slaBreachesAt=(NOW + timedelta(days=30)).isoformat(),
            )
            item = sync()
            assert item.linear_due_date == NOW.date() + timedelta(days=3)
            assert item.linear_sla_breaches_at == NOW + timedelta(days=30)
            assert item.deadline_source == "linear_due_date"

            raw["dueDate"] = None
            item = sync()
            assert item.linear_due_date is None
            assert item.deadline == NOW + timedelta(days=30)
            assert item.deadline_source == "linear_sla"

            raw.update(slaBreachesAt=None, priority=0)
            item = sync()
            assert item.linear_sla_breaches_at is None
            assert item.deadline is None
            assert item.deadline_source is None
            get_service.return_value.update_issue.assert_not_called()

    def test_failed_sync_does_not_advance_freshness(self, dashboard):
        _, _, incident = dashboard
        old_sync = NOW - timedelta(days=2)
        incident.action_items_last_synced_at = old_sync
        incident.save()
        with patch("firetower.incidents.services._get_linear_service") as get_service:
            get_service.return_value.get_child_issues.return_value = None
            stats = sync_action_items_from_linear(incident, force=True)
        incident.refresh_from_db()
        assert stats.errors
        assert incident.action_items_last_synced_at == old_sync

    def test_hourly_sweep_includes_old_closed_low_severity_incidents_and_continues_after_failure(
        self, dashboard
    ):
        _, _, recent = dashboard
        old = Incident.objects.create(
            title="Old completed incident",
            status="Done",
            severity="P4",
            linear_parent_issue_id="old",
        )
        Incident.objects.filter(pk=old.pk).update(created_at=NOW - timedelta(days=500))
        Incident.objects.create(
            title="Canceled",
            severity="P1",
            status="Canceled",
            linear_parent_issue_id="canceled",
        )
        Incident.objects.create(title="Unlinked", severity="P1")
        Incident.objects.create(
            title="Empty parent", severity="P1", linear_parent_issue_id=""
        )
        with patch(
            "firetower.incidents.tasks.action_items.sync_action_items_from_linear",
            side_effect=[RuntimeError("upstream"), ActionItemsSyncStats()],
        ) as sync:
            refresh_action_item_dashboard.__wrapped__()
        assert {call.args[0].id for call in sync.call_args_list} == {recent.id, old.id}

    def test_sweep_disabled_without_linear(self, settings):
        settings.LINEAR = None
        with patch(
            "firetower.incidents.tasks.action_items.sync_action_items_from_linear"
        ) as sync:
            refresh_action_item_dashboard.__wrapped__()
        sync.assert_not_called()

    def test_schedule_is_hourly_and_reversible(self):
        migration = import_module(
            "firetower.incidents.migrations.0026_action_item_dashboard"
        )
        schedule = Schedule.objects.get(name=migration.SCHEDULE_NAME)
        assert schedule.minutes == 60
        assert schedule.repeats == -1
        migration.delete_schedule(apps, None)
        assert not Schedule.objects.filter(name=migration.SCHEDULE_NAME).exists()
        migration.create_schedule(apps, None)
        migration.create_schedule(apps, None)
        assert Schedule.objects.filter(name=migration.SCHEDULE_NAME).count() == 1
