# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1

FROM base AS build
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY src ./src
COPY data ./data

FROM base AS runtime
ARG UID=10001
RUN adduser --disabled-password --gecos "" --home /app --shell /sbin/nologin --uid "${UID}" appuser
WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app
USER appuser
CMD ["uv", "run", "--no-sync", "python", "-m", "tampa_phone.agent", "start"]
