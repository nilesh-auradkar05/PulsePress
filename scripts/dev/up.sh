#!/usr/bin/env bash
# Bring up the local PulsePress stack (Sprint 1: API only).
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose up --build -d
echo "API health: http://localhost:8000/healthz"
