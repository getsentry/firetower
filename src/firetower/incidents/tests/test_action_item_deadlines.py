from datetime import UTC, date, datetime, time, timedelta

import pytest

from firetower.incidents.models import ActionItem
from firetower.incidents.serializers import ActionItemSerializer

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


@pytest.fixture
def slo_settings(settings, _disable_linear):
    settings.LINEAR = {
        "ACTION_ITEM_SLO_DAYS_HIGH_PRIORITY": 14,
        "ACTION_ITEM_SLO_DAYS_MEDIUM_PRIORITY": 30,
    }
    return settings


@pytest.mark.parametrize("priority", [0, 1, 2, 3, 4])
def test_explicit_due_date_takes_precedence(slo_settings, priority):
    item = ActionItem(
        priority=priority,
        created_at=NOW - timedelta(days=20),
        linear_due_date=date(2026, 11, 20),
        linear_sla_breaches_at=NOW - timedelta(days=1),
    )
    assert item.deadline == datetime(2026, 11, 20, 23, 59, 59, 999999, tzinfo=UTC)
    assert item.deadline_source == "linear_due_date"
    assert ActionItemSerializer().get_slo_deadline(item) == item.deadline.isoformat()


@pytest.mark.parametrize("priority", [0, 1, 2, 3, 4])
def test_linear_sla_overrides_recomputed_priority_target(slo_settings, priority):
    item = ActionItem(
        priority=priority,
        created_at=NOW - timedelta(days=20),
        linear_sla_breaches_at=NOW + timedelta(days=9),
    )
    assert item.deadline == NOW + timedelta(days=9)
    assert item.deadline_source == "linear_sla"


@pytest.mark.parametrize(
    "priority,days", [(1, 14), (2, 14), (3, 30), (4, None), (0, None)]
)
def test_priority_fallback_only_when_linear_has_no_deadline(
    slo_settings, priority, days
):
    item = ActionItem(priority=priority, created_at=NOW)
    assert item.deadline == (NOW + timedelta(days=days) if days else None)
    assert item.deadline_source == ("priority_slo" if days else None)


def test_removing_dates_reveals_remaining_fallbacks(slo_settings):
    item = ActionItem(
        priority=2,
        created_at=NOW,
        linear_due_date=date(2026, 11, 18),
        linear_sla_breaches_at=NOW + timedelta(days=5),
    )
    item.linear_due_date = None
    assert item.deadline == NOW + timedelta(days=5)
    assert item.deadline_source == "linear_sla"
    item.linear_sla_breaches_at = None
    assert item.deadline == NOW + timedelta(days=14)
    assert item.deadline_source == "priority_slo"
    item.priority = 0
    assert item.deadline is None
    assert item.deadline_source is None


def test_date_only_deadlines_include_the_entire_utc_day(slo_settings):
    item = ActionItem(linear_due_date=NOW.date())
    assert item.deadline == datetime.combine(NOW.date(), time.max, tzinfo=UTC)
    assert item.deadline > NOW
    assert item.deadline < datetime(2026, 11, 18, tzinfo=UTC)


def test_real_linear_deadlines_do_not_depend_on_slo_configuration(settings):
    settings.LINEAR = None
    item = ActionItem(linear_sla_breaches_at=NOW)
    assert item.deadline == NOW
    assert item.deadline_source == "linear_sla"
    item.linear_due_date = NOW.date()
    assert item.deadline == datetime.combine(NOW.date(), time.max, tzinfo=UTC)
    assert item.deadline_source == "linear_due_date"
