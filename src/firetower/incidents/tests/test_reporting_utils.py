from datetime import UTC, datetime

import pytest
from django.contrib.auth.models import User

from firetower.incidents.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Tag,
    TagType,
)
from firetower.incidents.reporting_utils import (
    build_incidents_by_tag,
    compute_regions,
    get_month_periods,
    get_quarter_periods,
    get_year_periods,
)


class TestGetMonthPeriods:
    def test_returns_12_periods(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        periods = get_month_periods(now)
        assert len(periods) == 12

    def test_most_recent_first(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        periods = get_month_periods(now)
        assert periods[0]["label"] == "March 2026"
        assert periods[1]["label"] == "February 2026"
        assert periods[11]["label"] == "April 2025"

    def test_start_end_bounds(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        march = get_month_periods(now)[0]
        assert march["start"] == datetime(2026, 3, 1, tzinfo=UTC)
        assert march["end"] == datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)

    def test_handles_year_boundary(self):
        now = datetime(2026, 1, 10, tzinfo=UTC)
        periods = get_month_periods(now)
        assert periods[0]["label"] == "January 2026"
        assert periods[1]["label"] == "December 2025"

    def test_february_leap_year(self):
        now = datetime(2024, 2, 15, tzinfo=UTC)
        feb = get_month_periods(now)[0]
        assert feb["end"].day == 29

    def test_february_non_leap_year(self):
        now = datetime(2025, 2, 15, tzinfo=UTC)
        feb = get_month_periods(now)[0]
        assert feb["end"].day == 28


class TestGetQuarterPeriods:
    def test_returns_8_periods(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        periods = get_quarter_periods(now)
        assert len(periods) == 8

    def test_fiscal_quarter_labels(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        periods = get_quarter_periods(now)
        assert periods[0]["label"] == "Q1 FY2026"

    def test_january_is_q4_of_previous_fy(self):
        now = datetime(2026, 1, 15, tzinfo=UTC)
        periods = get_quarter_periods(now)
        assert periods[0]["label"] == "Q4 FY2025"

    def test_q1_bounds(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        q1 = get_quarter_periods(now)[0]
        assert q1["start"] == datetime(2026, 2, 1, tzinfo=UTC)
        assert q1["end"] == datetime(2026, 4, 30, 23, 59, 59, 999999, tzinfo=UTC)


class TestGetYearPeriods:
    def test_returns_3_periods(self):
        now = datetime(2026, 3, 15, tzinfo=UTC)
        periods = get_year_periods(now)
        assert len(periods) == 3

    def test_fiscal_year_labels(self):
        now = datetime(2026, 6, 1, tzinfo=UTC)
        periods = get_year_periods(now)
        assert periods[0]["label"] == "FY2026"
        assert periods[1]["label"] == "FY2025"
        assert periods[2]["label"] == "FY2024"

    def test_fy_bounds(self):
        now = datetime(2026, 6, 1, tzinfo=UTC)
        fy = get_year_periods(now)[0]
        assert fy["start"] == datetime(2026, 2, 1, tzinfo=UTC)
        assert fy["end"] == datetime(2027, 1, 31, 23, 59, 59, 999999, tzinfo=UTC)

    def test_january_uses_previous_fy(self):
        now = datetime(2026, 1, 15, tzinfo=UTC)
        periods = get_year_periods(now)
        assert periods[0]["label"] == "FY2025"


@pytest.mark.django_db
class TestComputeRegions:
    @pytest.fixture()
    def user(self):
        return User.objects.create_user(username="test@example.com")

    @pytest.fixture()
    def region_tag(self):
        return Tag.objects.create(name="us-east-1", type=TagType.AFFECTED_REGION)

    @pytest.fixture()
    def make_incident(self, user, region_tag):
        def _make(created_at, total_downtime=None):
            inc = Incident.objects.create(
                title="Test",
                status=IncidentStatus.ACTIVE,
                severity=IncidentSeverity.P1,
                captain=user,
                reporter=user,
                total_downtime=total_downtime,
            )
            # auto_now_add ignores passed values, so update separately
            Incident.objects.filter(pk=inc.pk).update(created_at=created_at)
            inc.refresh_from_db()
            inc.affected_region_tags.add(region_tag)
            return inc

        return _make

    def test_100_percent_availability_with_no_incidents(self, region_tag):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 4, 1, tzinfo=UTC)

        regions = compute_regions([region_tag], period_start, period_end, now, {})
        assert len(regions) == 1
        assert regions[0]["availability_percentage"] == 100.0
        assert regions[0]["incident_count"] == 0

    def test_availability_with_downtime(self, region_tag, make_incident):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 4, 1, tzinfo=UTC)

        inc = make_incident(datetime(2026, 3, 10, tzinfo=UTC), total_downtime=60)
        incidents_by_tag = build_incidents_by_tag([inc])

        regions = compute_regions(
            [region_tag], period_start, period_end, now, incidents_by_tag
        )
        assert regions[0]["availability_percentage"] < 100.0
        assert regions[0]["total_downtime_minutes"] == 60
        assert regions[0]["incident_count"] == 1

    def test_uses_effective_end_for_current_period(self, region_tag):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 3, 4, tzinfo=UTC)

        regions = compute_regions([region_tag], period_start, period_end, now, {})
        # With no downtime, availability should be exactly 100% even for partial period
        assert regions[0]["availability_percentage"] == 100.0

    def test_excludes_incidents_outside_period(self, region_tag, make_incident):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 4, 1, tzinfo=UTC)

        inc = make_incident(datetime(2026, 2, 15, tzinfo=UTC), total_downtime=60)
        incidents_by_tag = build_incidents_by_tag([inc])

        regions = compute_regions(
            [region_tag], period_start, period_end, now, incidents_by_tag
        )
        assert regions[0]["incident_count"] == 0
        assert regions[0]["availability_percentage"] == 100.0

    def test_division_by_zero_returns_empty(self, region_tag):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, tzinfo=UTC)
        now = period_start  # effective_end == period_start -> 0 seconds

        regions = compute_regions([region_tag], period_start, period_end, now, {})
        assert regions == []

    def test_availability_floors_at_zero(self, region_tag, make_incident):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 4, 1, tzinfo=UTC)

        # 999999 minutes of downtime far exceeds the period
        inc = make_incident(datetime(2026, 3, 10, tzinfo=UTC), total_downtime=999999)
        incidents_by_tag = build_incidents_by_tag([inc])

        regions = compute_regions(
            [region_tag], period_start, period_end, now, incidents_by_tag
        )
        assert regions[0]["availability_percentage"] == 0.0

    def test_ignores_incidents_with_null_downtime(self, region_tag, make_incident):
        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 4, 1, tzinfo=UTC)

        inc = make_incident(datetime(2026, 3, 10, tzinfo=UTC), total_downtime=None)
        incidents_by_tag = build_incidents_by_tag([inc])

        regions = compute_regions(
            [region_tag], period_start, period_end, now, incidents_by_tag
        )
        assert regions[0]["availability_percentage"] == 100.0
        assert regions[0]["total_downtime_minutes"] == 0
        assert regions[0]["incident_count"] == 1

    def test_multiple_regions(self, user):
        tag_a = Tag.objects.create(name="us-east-1", type=TagType.AFFECTED_REGION)
        tag_b = Tag.objects.create(name="eu-west-1", type=TagType.AFFECTED_REGION)

        period_start = datetime(2026, 3, 1, tzinfo=UTC)
        period_end = datetime(2026, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
        now = datetime(2026, 4, 1, tzinfo=UTC)

        inc = Incident.objects.create(
            title="Test",
            status=IncidentStatus.ACTIVE,
            severity=IncidentSeverity.P1,
            captain=user,
            reporter=user,
            total_downtime=60,
        )
        Incident.objects.filter(pk=inc.pk).update(
            created_at=datetime(2026, 3, 10, tzinfo=UTC)
        )
        inc.refresh_from_db()
        inc.affected_region_tags.add(tag_a)
        incidents_by_tag = build_incidents_by_tag([inc])

        regions = compute_regions(
            [tag_a, tag_b], period_start, period_end, now, incidents_by_tag
        )
        assert len(regions) == 2
        assert regions[0]["name"] == "us-east-1"
        assert regions[0]["incident_count"] == 1
        assert regions[1]["name"] == "eu-west-1"
        assert regions[1]["incident_count"] == 0
        assert regions[1]["availability_percentage"] == 100.0
