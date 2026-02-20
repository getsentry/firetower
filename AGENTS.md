We use uv for backend stuff: uv run pytest, uv run manage.py runserver, etc. Backend dependencies are managed in pyproject.toml with uv.lock as the lockfile.

We use bun for frontend stuff: bun dev, bun test, bun run lint, bun run format, etc.

Make sure you do not use NODE_ENV=production when running bun test.

In the frontend, prefer using types that are defined alongside the tanstack query query options as zod schemas over redefining types locally.

Try to use semantically correct html tags whenever possible.

Please don't add comments to explain code unless it's overly obscure. Default to no comments. Docstrings are fine.

Always use log level info instead of debug.

In python, use top level imports unless absolutely necessary.

Use browser native focus styles for everything unless otherwise stated.

Do not skip precommit checks.
