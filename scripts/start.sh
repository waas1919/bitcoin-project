#!/bin/sh
# Start both nodes, mine on 2 cores, start the dashboard.
# The chain lives in Docker volumes, so this resumes where you stopped.
set -eu

MINER_CORES=2
RPC_WAIT_S=60
DASHBOARD_URL=http://127.0.0.1:8011

ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/dashboard.pid"
cd "$ROOT"
mkdir -p "$RUN_DIR"

echo "starting nodes (first run builds the image, takes a few minutes)..."
docker compose up -d

echo "waiting for satoshi RPC..."
i=0
until ./scripts/cli.sh satoshi getinfo >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge "$RPC_WAIT_S" ]; then
        echo "satoshi did not answer after ${RPC_WAIT_S}s. See: docker compose logs satoshi" >&2
        exit 1
    fi
    sleep 1
done

./scripts/cli.sh satoshi setgenerate true "$MINER_CORES" >/dev/null
echo "satoshi mining on $MINER_CORES cores"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "dashboard already running"
else
    nohup python3 "$ROOT/dashboard/server.py" >"$RUN_DIR/dashboard.log" 2>&1 &
    echo $! >"$PID_FILE"
fi
echo "dashboard: $DASHBOARD_URL"
echo "stop with: ./scripts/stop.sh"
