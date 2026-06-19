# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12-slim-bookworm

FROM python:${PYTHON_VERSION} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv


FROM base AS builder
WORKDIR /app
COPY pyproject.toml ./
# NB: two steps (compile -> file -> install) instead of `-r <(... )`. Docker RUN
# uses /bin/sh (dash), which has no process substitution, so `<(...)` errors out.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv \
    && uv pip compile pyproject.toml --quiet -o /tmp/requirements.txt \
    && uv pip install --python /opt/venv/bin/python -r /tmp/requirements.txt


FROM base AS dev
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/src"
COPY pyproject.toml ./
# Dependency-groups (PEP 735) are a uv *project* concept; `uv pip install --group`
# does not exist. Export the dev group to a requirements file, then pip-install it.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --only-group dev --format requirements-txt --no-emit-project --no-hashes \
      -o /tmp/dev-requirements.txt \
    && uv pip install --python /opt/venv/bin/python -r /tmp/dev-requirements.txt
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


FROM base AS runtime
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/src"
COPY --chown=app:app src ./src
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./alembic.ini
USER app
EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--forwarded-allow-ips", "*", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
