#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/harvester.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "Harvester is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "Harvester is not running (stale PID $PID — removing)"
    rm "$PID_FILE"
    exit 0
fi

echo "Stopping Harvester (PID $PID)..."
kill "$PID"

# Wait for clean shutdown (up to 5 seconds)
for _ in {1..10}; do
    if ! kill -0 "$PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

if kill -0 "$PID" 2>/dev/null; then
    echo "Process did not exit cleanly — sending SIGKILL"
    kill -9 "$PID"
fi

rm -f "$PID_FILE"
echo "Harvester stopped."
