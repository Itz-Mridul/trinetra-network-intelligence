#!/usr/bin/env bash
# Start a named portable field survey on the Pi's user-space tmux stack.
# Usage: PIPROBE_CARRIER=JIO bash start_survey.sh SITE_ID [LOCATION_ID] [SESSION_ID]
set -euo pipefail

PIPROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_ID="${1:-}"
LOCATION_ID="${2:-server_corner}"
SESSION_ID="${3:-session_$(date -u +%Y%m%dT%H%M%SZ)}"

if [[ -z "$SITE_ID" ]]; then
  echo "Usage: PIPROBE_CARRIER=JIO|BSNL $0 SITE_ID [LOCATION_ID] [SESSION_ID]" >&2
  exit 2
fi

if tmux has-session -t piprobe-wan 2>/dev/null; then
  tmux kill-session -t piprobe-wan
fi

export PIPROBE_SITE_ID="$SITE_ID"
export PIPROBE_SESSION_ID="$SESSION_ID"
export PIPROBE_LOCATION_ID="$LOCATION_ID"
bash "$PIPROBE_DIR/pi_scripts/start_piprobe_tmux.sh"

echo "Survey started: site=$SITE_ID session=$SESSION_ID location=$LOCATION_ID"
echo "Flash each ESP32 with the same site/session and its own probe/location ID."
