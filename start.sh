#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/harvester.pid"
LOG_DIR="$SCRIPT_DIR/data/logs"
LOG_FILE="$LOG_DIR/harvester.log"
CONFIG="$SCRIPT_DIR/harvester-config.yaml"
ENV_FILE="$SCRIPT_DIR/.env"

cd "$SCRIPT_DIR"

# Load .env if present
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

# Already running?
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Harvester is already running (PID $PID)"
        exit 0
    fi
    echo "Removing stale PID file..."
    rm "$PID_FILE"
fi

mkdir -p "$LOG_DIR"

echo "Starting Harvester..."
HARVESTER_CONFIG="$CONFIG" nohup uv run python -m harvester serve >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# Give it a moment then verify
sleep 2
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Harvester failed to start. Check $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

# Health check
PORT=$(uv run python -c "from harvester.config import load_config; c = load_config('$CONFIG'); print(c.settings.webhook_port)" 2>/dev/null || echo 8500)
if curl -sf "http://localhost:$PORT/healthz" > /dev/null 2>&1; then
    echo "Harvester running on port $PORT (PID $(cat "$PID_FILE"))"
    echo "Health: $(curl -s "http://localhost:$PORT/healthz")"
else
    echo "Harvester started (PID $(cat "$PID_FILE")) but /healthz not responding yet"
fi
echo "Logs: $LOG_FILE"
