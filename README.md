# Firetower

An incident management platform for tracking, triaging, and resolving incidents. Firetower provides severity and status classification, participant management, milestone tracking, and integrations with Slack.

## Tech Stack

- **Backend**: Django 5.2, Django REST Framework, PostgreSQL
- **Frontend**: React 19, TypeScript, TanStack Router/Query, Tailwind CSS, Radix UI
- **SDK**: Python SDK with JWT auth for programmatic access
- **Tooling**: uv (Python), Bun (JS), Docker Compose

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
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
bun install
bun dev
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
bun test
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

## Project Structure

```
src/firetower/       # Django backend
  incidents/         # Core incident models and API
  integrations/      # Slack
  auth/              # Authentication
frontend/            # React frontend
sdk/                 # Python SDK
```

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
