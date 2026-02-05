# Firetower

An incident management platform for tracking, triaging, and resolving incidents. Firetower provides severity and status classification, participant management, milestone tracking, and integrations with Slack, Jira, Datadog, and PagerDuty.

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

### Full Stack (Docker)

To run the full stack behind an nginx proxy:

```sh
docker compose up -d
```

The app will be available at http://localhost:8080.

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

```sh
# Backend
uv run ruff check .
uv run mypy .

# Frontend
cd frontend
bun run lint
bun run format
```

## Configuration

All configuration lives in `config.toml` (copy `config.example.toml` as a starting point). Sections include:

- **postgres**: Database connection
- **jira**: Jira integration
- **slack**: Slack bot token and team config
- **auth**: IAP authentication
- **datadog**: Datadog API keys

## Project Structure

```
src/firetower/       # Django backend
  incidents/         # Core incident models and API
  integrations/      # Slack, Jira, Datadog, PagerDuty
  auth/              # Authentication
frontend/            # React frontend
sdk/                 # Python SDK
```
