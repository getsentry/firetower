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
