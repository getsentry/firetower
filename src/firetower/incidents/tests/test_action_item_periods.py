from datetime import UTC, datetime, timedelta

import pytest

from firetower.incidents.action_item_periods import (
    TIME_RANGES,
    get_range_start,
    get_trend_periods,
)

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "key,expected",
    [
        ("7d", datetime(2026, 11, 10, 12, tzinfo=UTC)),
        ("14d", datetime(2026, 11, 3, 12, tzinfo=UTC)),
        ("1m", datetime(2026, 10, 17, 12, tzinfo=UTC)),
        ("3m", datetime(2026, 8, 17, 12, tzinfo=UTC)),
        ("6m", datetime(2026, 5, 17, 12, tzinfo=UTC)),
        ("9m", datetime(2026, 2, 17, 12, tzinfo=UTC)),
        ("12m", datetime(2025, 11, 17, 12, tzinfo=UTC)),
        ("all", None),
    ],
)
def test_presets(key, expected):
    assert get_range_start(key, NOW) == expected


@pytest.mark.parametrize(
    "now,key,expected",
    [
        (
            datetime(2026, 3, 31, 23, 30, tzinfo=UTC),
            "1m",
            datetime(2026, 2, 28, 23, 30, tzinfo=UTC),
        ),
        (
            datetime(2024, 3, 31, 12, tzinfo=UTC),
            "1m",
            datetime(2024, 2, 29, 12, tzinfo=UTC),
        ),
        (
            datetime(2024, 2, 29, 12, tzinfo=UTC),
            "12m",
            datetime(2023, 2, 28, 12, tzinfo=UTC),
        ),
        (
            datetime(2026, 1, 31, 12, tzinfo=UTC),
            "3m",
            datetime(2025, 10, 31, 12, tzinfo=UTC),
        ),
        (
            datetime(2026, 8, 31, 12, tzinfo=UTC),
            "6m",
            datetime(2026, 2, 28, 12, tzinfo=UTC),
        ),
    ],
)
def test_calendar_months_handle_month_end_and_leap_years(now, key, expected):
    assert get_range_start(key, now) == expected


@pytest.mark.parametrize(
    "key,interval,count",
    [
        ("7d", "Daily", 8),
        ("14d", "Daily", 15),
        ("1m", "Weekly", 6),
        ("3m", "Monthly", 4),
        ("6m", "Monthly", 7),
        ("9m", "Monthly", 10),
        ("12m", "Monthly", 13),
    ],
)
def test_periods_cover_ranges_without_gaps_or_overlap(key, interval, count):
    start = get_range_start(key, NOW)
    label, periods = get_trend_periods(start, NOW)
    assert label == interval
    assert len(periods) == count
    assert periods[0]["start"] <= start
    assert periods[-1]["end"] > NOW
    assert all(period["start"] < period["end"] for period in periods)
    assert all(a["end"] == b["start"] for a, b in zip(periods, periods[1:]))


def test_all_history_is_covered_with_a_bounded_number_of_periods():
    start = NOW.replace(year=2016)
    label, periods = get_trend_periods(start, NOW)
    assert label == "10-month periods"
    assert len(periods) <= 13
    assert periods[0]["start"] <= start
    assert periods[-1]["end"] > NOW


def test_empty_history_and_exact_midnight_still_have_a_current_bucket():
    _, empty = get_trend_periods(NOW, NOW)
    assert len(empty) == 1
    midnight = NOW.replace(hour=0)
    _, periods = get_trend_periods(midnight - timedelta(days=7), midnight)
    assert periods[-1]["start"] == midnight
    assert periods[-2]["end"] == midnight


def test_invalid_ranges_are_rejected():
    with pytest.raises(ValueError):
        get_range_start("30d", NOW)
    with pytest.raises(ValueError):
        get_trend_periods(NOW + timedelta(days=1), NOW)
    assert list(TIME_RANGES) == ["7d", "14d", "1m", "3m", "6m", "9m", "12m", "all"]
