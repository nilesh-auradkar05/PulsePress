#!/usr/bin/env bash
# Apply database migrations against the local stack's Postgres.
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose run --rm migrate
