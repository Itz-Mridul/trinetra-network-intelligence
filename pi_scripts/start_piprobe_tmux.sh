#!/usr/bin/env bash
# Start Trinetra's user-space processes in persistent tmux sessions.
set -u

PIPROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPROBE_SITE_ID="${PIPROBE_SITE_ID:-unassigned_site}"
PIPROBE_SESSION_ID="${PIPROBE_SESSION_ID:-}"
PIPROBE_LOCATION_ID="${PIPROBE_LOCATION_ID:-server_corner}"
PIPROBE_CARRIER="${PIPROBE_CARRIER:-}"

start_session() {
  local name="$1"
  local command="$2"
  if ! tmux has-session -t "$name" 2>/dev/null; then
    tmux new-session -d -s "$name" "$command"
  fi
}

start_session "piprobe-mqtt" \
  "cd '$PIPROBE_DIR' && MQTT_BROKER=localhost MQTT_TOPIC='piprobe/+/+' python3 '$PIPROBE_DIR/pi_scripts/mqtt_to_influx.py'"
start_session "piprobe-wan" \
  "cd '$PIPROBE_DIR' && PIPROBE_MQTT_BROKER=localhost PIPROBE_CARRIER='$PIPROBE_CARRIER' PIPROBE_SITE_ID='$PIPROBE_SITE_ID' PIPROBE_SESSION_ID='$PIPROBE_SESSION_ID' PIPROBE_LOCATION_ID='$PIPROBE_LOCATION_ID' python3 '$PIPROBE_DIR/pi_scripts/wan_probe.py'"
start_session "piprobe-dash" \
  "cd '$PIPROBE_DIR/dashboard' && python3 server.py"
