# Phase 13 / DASH-09: dashboard deployment image.
# Multi-purpose: any `uv run <script>` from pyproject.toml [project.scripts]
# can be the CMD. Default is `uv run dashboard`.
#
# Build context allow-list: only pyproject.toml, uv.lock, src/, migrations/,
# alembic.ini enter the image. No `COPY . .` — keeps .env, .planning/, tests/,
# .git out of the image (T-13-08 / T-13-10 mitigation, plus .dockerignore).
FROM python:3.12-slim

# Install uv (pinned to a known-good floor matching CLAUDE.md stack).
RUN pip install --no-cache-dir 'uv>=0.4'

WORKDIR /app

# Copy pyproject + lockfile first to maximize Docker layer caching.
COPY pyproject.toml uv.lock ./

# Copy source + migrations needed at runtime.
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

# Install the project itself. uv.lock exists at repo root, so --frozen is safe
# and gives reproducible builds.
RUN uv sync --no-dev --frozen

# Dashboard default; override CMD for other entrypoints (gateway, agent, all).
EXPOSE 8001
CMD ["uv", "run", "dashboard"]
