# PulsePress worker — minimal walking-skeleton image (Sprint 1).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY app ./app

CMD ["uv", "run", "--no-dev", "python", "-m", "app.main"]
