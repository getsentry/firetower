# Firetower

An incident management platform for tracking, triaging, and resolving incidents. Firetower provides severity and status classification, participant management, milestone tracking, and integrations with Slack.

## Tech Stack

- **Backend**: Django 5.2, Django REST Framework, PostgreSQL
- **Frontend**: React 19, TypeScript, TanStack Router/Query, StyleXJS, Radix UI
- **SDK**: Python SDK with JWT auth for programmatic access
- **Tooling**: uv (Python), pnpm (JS), Docker Compose

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/) 22+
- [Docker](https://www.docker.com/)

### Database

```sh
cp config.example.toml config.toml
# Edit config.toml with your values
docker compose -f docker-compose.db.yml up -d
uv run manage.py migrate
```

You can inspect the database with Adminer at http://localhost:8089.

### Backend

```sh
uv sync
uv run manage.py runserver
```

The API will be available at http://localhost:8000.

### Frontend

```sh
cd frontend
pnpm install
pnpm dev
```

The dev server will be available at http://localhost:5173.

### Local Slack App

Firetower's Slack integration uses [Socket Mode](https://api.slack.com/apis/socket-mode), so no public URL or tunnel is needed for local development.

#### 1. Create a Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and choose **Create New App > From a manifest**.
2. Select your development workspace.
3. Paste the contents of `slack-app-manifest.yaml`, using the `# test:` values commented beside each field (e.g. name `Firetower Test`, command `/ft-test`).
4. Install the app to your workspace when prompted.

#### 2. Collect tokens

From your app's settings page, grab two tokens and add them to `config.toml`:

| Token | Where to find it | config.toml key |
|---|---|---|
| **Bot token** (`xoxb-...`) | OAuth & Permissions > Bot User OAuth Token | `slack.bot_token` |
| **App-level token** (`xapp-...`) | Basic Information > App-Level Tokens (create one with the `connections:write` scope) | `slack.app_token` |

Also set `slack.team_id` to your workspace's team ID (visible in the workspace URL or via the Slack API).

#### 3. Configure a feed channel

Create or choose a Slack channel for incident notifications and set its ID as `slack.incident_feed_channel_id` in `config.toml`. Invite the bot to that channel.

#### 4. Run the bot

With the database and backend already running:

```sh
uv run manage.py run_slack_bot
```

The bot connects via WebSocket and registers the `/ft-test` and `/testinc` slash commands. Type `/ft-test help` in Slack to verify.

## Development

### Running Tests

```sh
# Backend
uv run pytest

# Frontend
cd frontend
pnpm test
```

### Linting & Formatting

Pre-commit is set up to handle all linting and formatting automatically. Install the hooks with:

```sh
uv run pre-commit install
```

This runs ruff, mypy, eslint, and prettier on commit, with knip on push.

## Configuration

All configuration lives in `config.toml` (copy `config.example.toml` as a starting point). Sections include:

- **postgres**: Database connection
- **slack**: Slack bot token and team config
- **auth**: IAP authentication
- **datadog**: Datadog metrics and event logging

Set `recent_incident_window_minutes` in `[slack]` to control how far back the incident-creation duplicate warning looks. It defaults to `10` minutes.

## Project Structure

```
src/firetower/       # Django backend
  incidents/         # Core incident models and API
  integrations/      # Slack
  auth/              # Authentication
frontend/            # React frontend
sdk/                 # Python SDK
```

## Incident Action Labels

Set `action_item_label_id` in the `[linear]` section of `config.toml` to the workspace-wide `incident-action` label's ID to enable automatic labeling during action item sync, including pre-existing issues adopted as follow-ups. Other labels are preserved. Labeling is skipped when the value is empty or omitted.

## Action Item Dashboard

The **Action Items** navigation tab summarizes cached Linear child issues across all visible, non-canceled incidents, including old and completed incidents. Time range and incident severity scope the full dashboard; queue view, Linear team, search, and pagination only narrow the follow-up queue. Global scope and queue filters are shareable in the URL. Team-progress controls filter and rank that table locally without changing the queue or refetching the report.

- **Health:** open work, overdue deadlines, items due within three days, missing owners/priorities, and issues with no Linear update for 14 days.
- **Progress:** creation/completion trends across the selected range in UTC, open backlog age, completions, median completion time, and on-time completion percentage. Charts use daily, weekly, or monthly periods, grouping long all-time histories into a bounded number of multi-month periods.
- **Team progress:** a leaderboard for the same creation-date cohort, defaulting to completed items, with searchable team and metric selectors for completions, completion rate, total work, open work, and overdue work. Completed-only teams remain visible. Total includes canceled items; completion rate is Done / (Done + Open), excluding canceled work. Unsynced team metadata is shown but is not ranked.
- **Triage:** a risk-ordered queue linking directly to Linear and the incident, plus a list of Linear teams with overdue/stalled work that drills into the queue without ranking individual assignees.

The global selector offers **7d, 14d, 1m, 3m, 6m, 9m, 12m, and All time** (the default). Finite ranges select follow-ups by their original **Linear creation time**, not the parent incident date or completion date; older open/overdue work and completions of older follow-ups are excluded. Choose All time for the full backlog. Day windows are rolling 24-hour periods; month windows subtract calendar months, clamping to month-end and preserving UTC time. Bounds are inclusive through report generation, and future-dated creations are excluded. All metrics, trends, team progress, and queue rows use this same cohort; integration sync coverage remains across all visible incidents. Range filtering happens in the database before loading action items; All time still loads all visible cached history.

Effective deadlines use this precedence: explicit Linear `dueDate` (through 23:59:59.999999 UTC on that date), then Linear `slaBreachesAt`, then the configured priority target from the issue's original creation time. Date and SLA edits or removals are copied on each sync; removing a due date falls back to the remaining SLA/priority target, not a stale cached date. Low and unset priorities have no priority-based fallback, but can have explicit dates or SLAs. Items without any deadline are excluded from overdue, due-soon, and on-time metrics but still contribute to open work, aging, and stalled counts. Canceled work is not a completion. Delivery metrics use Linear completion timestamps on currently completed issues, not historical transitions; reopened issues are excluded. Missing activity/completion timestamps are reported rather than inferred from Firetower sync times.

The read-only `GET /api/ui/action-items/` endpoint accepts `time_range` (`7d`, `14d`, `1m`, `3m`, `6m`, `9m`, `12m`, or `all`), `severity` (P0–P4), `view` (attention/open/overdue/due_soon/stalled/unassigned/no_priority), `team` (Linear team UUID or `unknown` for missing metadata), `q`, and a one-based `page`. The response includes resolved `time_range` bounds, range-scoped `created_count`/`completed_count` summary fields, and `trend.interval`/`trend.buckets`. Queue pages contain up to ten items. Every aggregate and row obeys the existing incident visibility rules; admin status does not bypass private-incident restrictions.

Migration 0026 adds nullable Linear activity/completion timestamps and an hourly Django-Q cache refresh for every linked, non-canceled incident, without an age or severity cutoff. Existing rows are backfilled by the next sync, with no external calls during migration or dashboard reads. The dashboard warns about never-synced incidents, syncs older than 24 hours, and missing activity dates. **Refresh dashboard** reloads the cache; use an incident's existing sync button to refresh that incident from Linear immediately.

Migration 0027 stores each child issue's actual Linear team ID, key, and name, backfilled on the next sync. Team grouping does not infer ownership from an identifier prefix or the parent incident's team. Until sync, missing metadata appears as **Team not synced**. The dashboard response, table, team breakdown, filter, and search do not expose individual assignee identities; individual assignees remain available on the incident detail view. Severity filtering reuses the incident page's editable pill selector. Queue and leaderboard dropdowns use a shared searchable Tag/Popover selector with keyboard navigation instead of native selects.

Migration 0028 caches Linear due dates and SLA deadlines. The legacy `slo_deadline` API field now returns the effective deadline in both incident detail and dashboard rows; dashboard `deadline_source` and `due_date` fields identify its origin. The existing automatic Linear SLA policy is unchanged. Linear edits appear after the hourly sync, or immediately after the incident's **Sync action items** action followed by a dashboard refresh. **Refresh dashboard** by itself only reloads the cache. On-time metrics compare completion against the currently synced deadline, not historical deadline versions.

## Scheduled Tasks

Scheduled tasks are stored as database objects and are managed via migrations.

### Adding a Task

First, define you task in the `SCHEDULES` map in `src/firetower/incidents/tasks.py`.

Then, create a new migration referencing it:

```python
from django.db import migrations

from firetower.incidents.tasks import SCHEDULES


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    schedule_name = "[schedule name goes here]"
    Schedule.objects.get_or_create(
        name=schedule_name, defaults=SCHEDULES[schedule_name]
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    schedule_name = "schedule_demo"
    Schedule.objects.filter(name=schedule_name).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "[previous migration goes here]"),
    ]

    operations = [
        migrations.RunPython(create_schedule, delete_schedule),
    ]
```

### Removing a task

First, generate the opposite of the migration used to add the schedule:

```python
from django.db import migrations

from firetower.incidents.tasks import SCHEDULES


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    schedule_name = "[schedule name goes here]"
    Schedule.objects.get_or_create(
        name=schedule_name, defaults=SCHEDULES[schedule_name]
    )


def delete_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    schedule_name = "schedule_demo"
    Schedule.objects.filter(name=schedule_name).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "[previous migration goes here]"),
    ]

    operations = [
        migrations.RunPython(delete_schedule, create_schedule),
    ]
```

Once this migration has run everywhere, you can then remove the body from the `SCHEDULES` array, but keep the key since these are still referenced in legacy migrations!

```python
SCHEDULES = {
    "schedule_demo": {
        # Removed in <migration name>
    },
}
```
