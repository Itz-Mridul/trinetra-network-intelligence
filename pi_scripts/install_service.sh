#!/bin/bash
# =================================================================
# Trinetra - Install wan_probe.py as a systemd auto-start service
# Run once after setup_pi.sh completes.
# =================================================================
set -e
PIPROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_SRC="$PIPROBE_DIR/pi_scripts/piprobe-wan.service"
SERVICE_DEST="/etc/systemd/system/piprobe-wan.service"
PIPROBE_USER="${SUDO_USER:-${USER}}"

# Update path in service file to actual project location
sudo cp "$SERVICE_SRC" "$SERVICE_DEST"
sudo sed -i \
  -e "s|__PIPROBE_USER__|$PIPROBE_USER|g" \
  -e "s|__PIPROBE_DIR__|$PIPROBE_DIR|g" \
  "$SERVICE_DEST"

sudo systemctl daemon-reload
sudo systemctl enable piprobe-wan.service
sudo systemctl start piprobe-wan.service

echo "=================================================="
echo "Service installed and started."
echo "Check status: sudo systemctl status piprobe-wan"
echo "View logs:    sudo journalctl -u piprobe-wan -f"
echo "=================================================="
