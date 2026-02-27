import calendar
from collections import defaultdict
from datetime import datetime
from datetime import tzinfo as TzInfo

from .models import Incident, Tag, format_downtime_minutes

_HISTORY_MONTHS = 12
_HISTORY_QUARTERS = 8
_HISTORY_YEARS = 3


def get_month_periods(now: datetime) -> list[dict]:
    periods = []
    year, month = now.year, now.month
    for _ in range(_HISTORY_MONTHS):
        last_day = calendar.monthrange(year, month)[1]
        start = now.replace(
            year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = now.replace(
            year=year,
            month=month,
            day=last_day,
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
        label = start.strftime("%B %Y")
        periods.append({"label": label, "start": start, "end": end})
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return periods


def _current_fiscal_quarter(now: datetime) -> tuple[int, int]:
    m = now.month
    if m == 1:
        return now.year - 1, 4
    elif m <= 4:
        return now.year, 1
    elif m <= 7:
        return now.year, 2
    elif m <= 10:
        return now.year, 3
    return now.year, 4


def _prev_fiscal_quarter(fy_year: int, quarter: int) -> tuple[int, int]:
    if quarter == 1:
        return fy_year - 1, 4
    return fy_year, quarter - 1


def _get_fiscal_quarter_bounds(
    fy_year: int, quarter: int, tzinfo: TzInfo
) -> tuple[datetime, datetime, str]:
    if quarter == 1:
        start = datetime(fy_year, 2, 1, tzinfo=tzinfo)
        end = datetime(fy_year, 4, 30, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q1 FY{fy_year}"
    elif quarter == 2:
        start = datetime(fy_year, 5, 1, tzinfo=tzinfo)
        end = datetime(fy_year, 7, 31, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q2 FY{fy_year}"
    elif quarter == 3:
        start = datetime(fy_year, 8, 1, tzinfo=tzinfo)
        end = datetime(fy_year, 10, 31, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q3 FY{fy_year}"
    else:
        start = datetime(fy_year, 11, 1, tzinfo=tzinfo)
        end = datetime(fy_year + 1, 1, 31, 23, 59, 59, 999999, tzinfo=tzinfo)
        label = f"Q4 FY{fy_year}"
    return start, end, label


def get_quarter_periods(now: datetime) -> list[dict]:
    periods = []
    fy_year, quarter = _current_fiscal_quarter(now)
    for _ in range(_HISTORY_QUARTERS):
        start, end, label = _get_fiscal_quarter_bounds(fy_year, quarter, now.tzinfo)  # type: ignore[arg-type]
        periods.append({"label": label, "start": start, "end": end})
        fy_year, quarter = _prev_fiscal_quarter(fy_year, quarter)
    return periods


def _current_fiscal_year(now: datetime) -> int:
    return now.year if now.month >= 2 else now.year - 1


def get_year_periods(now: datetime) -> list[dict]:
    periods = []
    fy_year = _current_fiscal_year(now)
    for _ in range(_HISTORY_YEARS):
        start = datetime(fy_year, 2, 1, tzinfo=now.tzinfo)
        end = datetime(fy_year + 1, 1, 31, 23, 59, 59, 999999, tzinfo=now.tzinfo)
        label = f"FY{fy_year}"
        periods.append({"label": label, "start": start, "end": end})
        fy_year -= 1
    return periods


def build_incidents_by_tag(
    incidents: list[Incident],
) -> dict[int, list[Incident]]:
    incidents_by_tag: dict[int, list[Incident]] = defaultdict(list)
    for incident in incidents:
        for tag in incident.affected_region_tags.all():
            incidents_by_tag[tag.id].append(incident)
    return incidents_by_tag


def compute_regions(
    tags: list[Tag],
    period_start: datetime,
    period_end: datetime,
    now: datetime,
    incidents_by_tag: dict[int, list[Incident]],
) -> list[dict]:
    effective_end = min(period_end, now)
    total_period_seconds = (period_end - period_start).total_seconds()
    regions = []
    for tag in tags:
        tag_incidents = [
            inc
            for inc in incidents_by_tag.get(tag.id, [])
            if period_start <= inc.created_at <= effective_end
        ]
        tag_incidents.sort(key=lambda inc: inc.created_at, reverse=True)
        # total_downtime is stored in minutes; convert to seconds for availability calculation
        total_downtime_minutes = sum(
            inc.total_downtime
            for inc in tag_incidents
            if inc.total_downtime is not None
        )
        total_downtime_seconds = total_downtime_minutes * 60
        availability_pct = max(
            0.0,
            (total_period_seconds - total_downtime_seconds)
            / total_period_seconds
            * 100,
        )
        incident_list = [
            {
                "id": inc.id,
                "title": inc.title,
                "created_at": inc.created_at.isoformat(),
                "total_downtime_minutes": inc.total_downtime,
                "total_downtime_display": inc.total_downtime_display,
            }
            for inc in tag_incidents
        ]
        regions.append(
            {
                "name": tag.name,
                "total_downtime_minutes": total_downtime_minutes,
                "total_downtime_display": format_downtime_minutes(
                    total_downtime_minutes
                ),
                "availability_percentage": round(availability_pct, 6),
                "incident_count": len(incident_list),
                "incidents": incident_list,
            }
        )
    return regions
