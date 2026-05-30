#!/usr/bin/env bash
# Tear down the local PulsePress stack. Pass extra args through (e.g. -v).
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose down "$@"
