from collections import Counter
from datetime import UTC, datetime, timedelta
from math import ceil
from statistics import median
from typing import Any

from django.db.models import QuerySet

from .action_item_periods import (
    AUTO_REFRESH_MONTHS,
    TIME_RANGES,
    get_auto_refresh_cutoff,
    get_range_start,
    get_trend_periods,
)
from .models import ActionItem, ActionItemStatus, Incident
from .serializers import DashboardActionItemSerializer

STALLED_DAYS = 14
DUE_SOON_DAYS = 3
PAGE_SIZE = 10


def build_action_item_dashboard(
    incidents: QuerySet[Incident],
    *,
    now: datetime,
    time_range: str = "all",
    view: str = "attention",
    team: str = "",
    q: str = "",
    page: int = 1,
) -> dict[str, Any]:
    """Report on cached follow-ups, scoped to incidents the caller can see."""
    now = now.astimezone(UTC)
    range_start = get_range_start(time_range, now)
    item_queryset = ActionItem.objects.filter(
        incident__in=incidents, created_at__lte=now
    )
    if range_start is not None:
        item_queryset = item_queryset.filter(created_at__gte=range_start)
    items = list(item_queryset.select_related("incident").order_by("created_at", "id"))
    incident_rows = list(
        incidents.only(
            "created_at", "linear_parent_issue_id", "action_items_last_synced_at"
        )
    )
    open_items = [
        item
        for item in items
        if item.status in (ActionItemStatus.TODO, ActionItemStatus.IN_PROGRESS)
    ]
    flags: dict[int, dict[str, bool]] = {}
    for item in open_items:
        deadline = item.deadline
        flags[item.id] = {
            "overdue": deadline is not None and deadline <= now,
            "due_soon": deadline is not None
            and now < deadline <= now + timedelta(days=DUE_SOON_DAYS),
            "stalled": item.linear_updated_at is not None
            and item.linear_updated_at <= now - timedelta(days=STALLED_DAYS),
            "unassigned": item.assignee_id is None,
            "no_priority": item.priority == 0,
        }

    completed = [
        item
        for item in items
        if item.status == ActionItemStatus.DONE
        and item.completed_at is not None
        and item.completed_at <= now
        and item.completed_at >= item.created_at
    ]
    completion_days = [
        (item.completed_at - item.created_at).total_seconds() / 86400
        for item in completed
        if item.completed_at is not None
    ]
    with_target = [item for item in completed if item.deadline is not None]
    on_time = sum(
        item.completed_at <= item.deadline
        for item in with_target
        if item.completed_at is not None and item.deadline is not None
    )
    counts = Counter(item.status for item in items)
    summary = {
        "open": len(open_items),
        "in_progress": counts[ActionItemStatus.IN_PROGRESS],
        "todo": counts[ActionItemStatus.TODO],
        "done": counts[ActionItemStatus.DONE],
        "canceled": counts[ActionItemStatus.CANCELED],
        "high_priority_open": sum(item.priority in (1, 2) for item in open_items),
        **{
            key: sum(item_flags[key] for item_flags in flags.values())
            for key in ("overdue", "due_soon", "stalled", "unassigned", "no_priority")
        },
        "attention": sum(any(item_flags.values()) for item_flags in flags.values()),
        "created_count": len(items),
        "completed_count": len(completed),
        "median_completion_days": round(median(completion_days), 1)
        if completion_days
        else None,
        "on_time_percent": round(on_time * 100 / len(with_target), 1)
        if with_target
        else None,
        "on_time_sample": len(with_target),
        "unknown_activity": sum(item.linear_updated_at is None for item in open_items),
        "unknown_team": sum(not item.linear_team_id for item in open_items),
        "unknown_completion": sum(
            item.status == ActionItemStatus.DONE and item.completed_at is None
            for item in items
        ),
    }

    trend_start = (
        range_start
        if range_start is not None
        else (items[0].created_at if items else now)
    )
    trend_interval, periods = get_trend_periods(trend_start, now)
    trend = [
        {
            "start": period["start"].isoformat(),
            "end": period["end"].isoformat(),
            "label": period["label"],
            "created": sum(
                period["start"] <= item.created_at < period["end"] for item in items
            ),
            "completed": sum(
                period["start"] <= item.completed_at < period["end"]
                for item in completed
                if item.completed_at is not None
            ),
        }
        for period in periods
    ]

    aging = []
    for label, lower, upper in [
        ("0–7 days", 0, 8),
        ("8–14 days", 8, 15),
        ("15–30 days", 15, 31),
        ("31–60 days", 31, 61),
        ("61+ days", 61, None),
    ]:
        bucket = [
            item
            for item in open_items
            if max(0, (now - item.created_at).days) >= lower
            and (upper is None or max(0, (now - item.created_at).days) < upper)
        ]
        aging.append(
            {
                "label": label,
                "count": len(bucket),
                "overdue": sum(flags[item.id]["overdue"] for item in bucket),
            }
        )

    teams: dict[str, dict[str, Any]] = {}
    for item in items:
        key = item.linear_team_id or "unknown"
        group = teams.setdefault(
            key,
            {
                "id": key,
                "key": item.linear_team_key,
                "name": (
                    item.linear_team_name
                    or item.linear_team_key
                    or "Unnamed Linear team"
                )
                if item.linear_team_id
                else "Team not synced",
                "open": 0,
                "overdue": 0,
                "stalled": 0,
                "completed": 0,
                "canceled": 0,
                "total": 0,
            },
        )
        group["total"] += 1
        if item.status == ActionItemStatus.DONE:
            group["completed"] += 1
        elif item.status == ActionItemStatus.CANCELED:
            group["canceled"] += 1
        elif item.id in flags:
            group["open"] += 1
            group["overdue"] += flags[item.id]["overdue"]
            group["stalled"] += flags[item.id]["stalled"]
    for group in teams.values():
        active_total = group["completed"] + group["open"]
        group["completion_rate"] = (
            round(group["completed"] * 100 / active_total, 1) if active_total else None
        )
    team_rows = sorted(
        teams.values(),
        key=lambda group: (
            -group["overdue"],
            -group["stalled"],
            -group["open"],
            group["name"],
            group["id"],
        ),
    )

    queue = [
        item
        for item in open_items
        if view == "open"
        or (view == "attention" and any(flags[item.id].values()))
        or flags[item.id].get(view, False)
    ]
    if team:
        queue = [item for item in queue if (item.linear_team_id or "unknown") == team]
    if q:
        needle = q.casefold()
        queue = [
            item
            for item in queue
            if needle
            in " ".join(
                [
                    item.title,
                    item.linear_identifier,
                    item.incident.incident_number,
                    item.incident.title,
                    item.linear_team_name,
                    item.linear_team_key,
                ]
            ).casefold()
        ]

    def risk_order(item: ActionItem) -> tuple:
        reasons = flags[item.id]
        rank = next(
            (
                index
                for index, key in enumerate(
                    ("overdue", "due_soon", "stalled", "unassigned", "no_priority")
                )
                if reasons[key]
            ),
            5,
        )
        return rank, item.priority or 5, item.created_at, item.id

    queue.sort(key=risk_order)
    pages = max(1, ceil(len(queue) / PAGE_SIZE))
    page = min(page, pages)
    page_items = queue[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    serializer = DashboardActionItemSerializer()
    rows = [
        {
            **serializer.to_representation(item),
            "age_days": max(0, (now - item.created_at).days),
            "idle_days": max(0, (now - item.linear_updated_at).days)
            if item.linear_updated_at
            else None,
            "flags": [key for key, active in flags[item.id].items() if active],
        }
        for item in page_items
    ]
    linked = [incident for incident in incident_rows if incident.linear_parent_issue_id]
    refresh_cutoff = get_auto_refresh_cutoff(now)
    refresh_eligible = [
        incident for incident in linked if incident.created_at >= refresh_cutoff
    ]
    eligible_syncs = [
        incident.action_items_last_synced_at
        for incident in refresh_eligible
        if incident.action_items_last_synced_at
    ]
    syncs = [
        incident.action_items_last_synced_at
        for incident in linked
        if incident.action_items_last_synced_at
    ]
    return {
        "generated_at": now.isoformat(),
        "time_range": {
            "key": time_range,
            "label": TIME_RANGES[time_range],
            "start": range_start.isoformat() if range_start is not None else None,
            "end": now.isoformat(),
        },
        "stalled_days": STALLED_DAYS,
        "due_soon_days": DUE_SOON_DAYS,
        "summary": summary,
        "trend": {"interval": trend_interval, "buckets": trend},
        "aging": aging,
        "teams": team_rows,
        "freshness": {
            "linked_incidents": len(linked),
            "unlinked_incidents": len(incident_rows) - len(linked),
            "auto_refresh_months": AUTO_REFRESH_MONTHS,
            "auto_refresh_cutoff": refresh_cutoff.isoformat(),
            "outside_refresh_window_incidents": len(linked) - len(refresh_eligible),
            "unsynced_incidents": len(refresh_eligible) - len(eligible_syncs),
            "stale_incidents": sum(
                sync < now - timedelta(days=1) for sync in eligible_syncs
            ),
            "oldest_sync_at": min(syncs).isoformat() if syncs else None,
        },
        "queue": {"count": len(queue), "page": page, "pages": pages, "results": rows},
    }
