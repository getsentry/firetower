import calendar
from datetime import datetime, timedelta
from math import ceil
from typing import Any

TIME_RANGES = {
    "7d": "Last 7 days",
    "14d": "Last 14 days",
    "1m": "Last month",
    "3m": "Last 3 months",
    "6m": "Last 6 months",
    "9m": "Last 9 months",
    "12m": "Last 12 months",
    "all": "All time",
}


def shift_months(value: datetime, months: int) -> datetime:
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return value.replace(
        year=year,
        month=month,
        day=min(value.day, calendar.monthrange(year, month)[1]),
    )


def get_range_start(key: str, now: datetime) -> datetime | None:
    if key not in TIME_RANGES:
        raise ValueError("Invalid dashboard time range")
    if key == "all":
        return None
    if key.endswith("d"):
        return now - timedelta(days=int(key[:-1]))
    return shift_months(now, -int(key[:-1]))


def get_trend_periods(
    start: datetime, end: datetime
) -> tuple[str, list[dict[str, Any]]]:
    """Build calendar-aligned UTC periods covering the selected window."""
    if start > end:
        raise ValueError("Start must not be after end")
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    duration = end - start
    months = 0
    if duration <= timedelta(days=14):
        interval = "Daily"
        step = timedelta(days=1)
    elif duration <= timedelta(days=45):
        interval = "Weekly"
        cursor -= timedelta(days=cursor.weekday())
        step = timedelta(weeks=1)
    else:
        cursor = cursor.replace(day=1)
        month_count = (end.year - cursor.year) * 12 + end.month - cursor.month + 1
        months = max(1, ceil(month_count / 13))
        interval = "Monthly" if months == 1 else f"{months}-month periods"
        step = timedelta(0)
    periods = []
    while cursor <= end:
        following = shift_months(cursor, months) if months else cursor + step
        label = (
            cursor.strftime("%b %Y")
            if months
            else f"{cursor.strftime('%b')} {cursor.day}"
        )
        periods.append({"start": cursor, "end": following, "label": label})
        cursor = following
    return interval, periods
