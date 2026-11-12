#!/bin/sh
# Stop the dashboard and both nodes. Keeps the chain and wallets (volumes).
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PID_FILE="$ROOT/.run/dashboard.pid"
cd "$ROOT"

if [ -f "$PID_FILE" ]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "dashboard stopped"
fi

# SIGTERM -> bitcoind HandleSIGTERM -> clean shutdown, database flushed.
docker compose stop
echo "nodes stopped, chain kept. Start again with ./scripts/start.sh"
