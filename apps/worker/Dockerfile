# PulsePress worker — outbox delivery and ledger processing service.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY app ./app
COPY pulsepress_worker ./pulsepress_worker

CMD ["uv", "run", "--no-dev", "python", "-m", "pulsepress_worker.main"]
