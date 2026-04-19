#!/usr/bin/env bash
# ==============================================================================
# Harvester — launchd plist installer
# ==============================================================================
# Writes two launchd plists to ~/Library/LaunchAgents/ and loads them:
#
#   com.hackstert.harvester          — FastAPI server (continuous, kept alive)
#   com.hackstert.harvester.runner   — Overnight agent runner (02:00 daily)
#
# Must be run from the Harvester repo root, or set HARVESTER_ROOT.
# ==============================================================================

set -euo pipefail

HARVESTER_ROOT="${HARVESTER_ROOT:-$(pwd)}"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HARVESTER_ROOT/data/logs"

# Confirm we're in the right place
if [[ ! -f "$HARVESTER_ROOT/harvester-config.yaml" ]]; then
    echo "ERROR: harvester-config.yaml not found under $HARVESTER_ROOT"
    echo "Run this script from the Harvester repo root, or set HARVESTER_ROOT"
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"

# Build a PATH that includes all the tools we need at 02:00 when the shell
# environment is minimal.
AGENT_PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Detect uv location
UV_PATH="$(command -v uv 2>/dev/null || echo "/opt/homebrew/bin/uv")"

echo "==> Harvester root: $HARVESTER_ROOT"
echo "==> LaunchAgents dir: $LAUNCH_AGENTS_DIR"
echo "==> uv location: $UV_PATH"

# ------------------------------------------------------------------------------
# Plist 1: FastAPI server — runs continuously, restarted if it crashes
# ------------------------------------------------------------------------------

SERVER_PLIST="$LAUNCH_AGENTS_DIR/com.hackstert.harvester.plist"

cat > "$SERVER_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hackstert.harvester</string>

  <key>ProgramArguments</key>
  <array>
    <string>$UV_PATH</string>
    <string>run</string>
    <string>python</string>
    <string>-m</string>
    <string>harvester</string>
    <string>serve</string>
    <string>--config</string>
    <string>$HARVESTER_ROOT/harvester-config.yaml</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$HARVESTER_ROOT</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$AGENT_PATH</string>
    <key>HOME</key>
    <string>$HOME</string>
  </dict>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/harvester-server.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/harvester-server-error.log</string>

  <!-- Restart automatically if the process exits -->
  <key>KeepAlive</key>
  <true/>

  <!-- Wait 10 seconds between restart attempts -->
  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
PLIST

echo "==> Wrote $SERVER_PLIST"

# ------------------------------------------------------------------------------
# Plist 2: Overnight agent runner — fires at 02:00 local time daily
# ------------------------------------------------------------------------------

RUNNER_PLIST="$LAUNCH_AGENTS_DIR/com.hackstert.harvester.runner.plist"

cat > "$RUNNER_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hackstert.harvester.runner</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$HARVESTER_ROOT/scripts/agent-runner.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$HARVESTER_ROOT</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$AGENT_PATH</string>
    <key>HOME</key>
    <string>$HOME</string>
    <key>HARVESTER_ROOT</key>
    <string>$HARVESTER_ROOT</string>
  </dict>

  <!-- Fire at 02:00 local time every day -->
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>2</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/agent-runner-launchd.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/agent-runner-launchd-error.log</string>

  <!-- Do not restart on exit — the runner is a one-shot job -->
  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
PLIST

echo "==> Wrote $RUNNER_PLIST"

# ------------------------------------------------------------------------------
# Load / reload both plists
# ------------------------------------------------------------------------------

load_plist() {
    local label="$1"
    local plist="$2"

    # Unload first if already loaded (silently ignore if not)
    launchctl unload "$plist" 2>/dev/null || true

    if launchctl load "$plist"; then
        echo "==> Loaded $label"
    else
        echo "ERROR: Failed to load $label"
        echo "       Check plist at: $plist"
        exit 1
    fi
}

load_plist "com.hackstert.harvester" "$SERVER_PLIST"
load_plist "com.hackstert.harvester.runner" "$RUNNER_PLIST"

echo ""
echo "==> Installation complete."
echo ""
echo "    FastAPI server:     com.hackstert.harvester (running now)"
echo "    Overnight runner:   com.hackstert.harvester.runner (fires at 02:00)"
echo ""
echo "    Verify server:      curl http://localhost:8500/healthz"
echo "    List jobs:          launchctl list | grep harvester"
echo "    Server logs:        tail -f $LOG_DIR/harvester-server.log"
echo "    Runner logs:        ls -lt $LOG_DIR/run-*.log | head -5"
echo ""
echo "    To unload:          launchctl unload $SERVER_PLIST"
echo "                        launchctl unload $RUNNER_PLIST"
