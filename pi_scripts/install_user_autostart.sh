#!/usr/bin/env bash
# Install Trinetra user-process autostart without requiring sudo.
set -e

PIPROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
START_SCRIPT="$PIPROBE_DIR/pi_scripts/start_piprobe_tmux.sh"
MARKER="# Trinetra user autostart"

chmod +x "$START_SCRIPT"
CURRENT_CRONTAB="$(crontab -l 2>/dev/null || true)"
if ! printf '%s\n' "$CURRENT_CRONTAB" | grep -Fq "$MARKER"; then
  {
    printf '%s\n' "$CURRENT_CRONTAB"
    printf '%s\n' "$MARKER"
    printf '@reboot /bin/sh -c '\''sleep 20; exec %s'\''\n' "$START_SCRIPT"
  } | crontab -
  echo "Installed Trinetra reboot autostart in the user crontab."
else
  echo "Trinetra reboot autostart is already installed."
fi

"$START_SCRIPT"
echo "Trinetra user processes are running in tmux sessions."
