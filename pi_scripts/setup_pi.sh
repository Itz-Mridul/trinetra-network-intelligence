#!/bin/bash
# =================================================================
# Trinetra - Raspberry Pi 5 One-Command Setup Script
# Run this ONCE on a fresh Raspberry Pi OS 64-bit Lite installation.
# It installs Docker, Python deps, iPerf2, NTP, and starts all services.
# Usage: curl -sSL <url>/setup_pi.sh | bash
#   OR:  bash setup_pi.sh
# =================================================================

set -e
echo "=================================================="
echo "   Trinetra Raspberry Pi 5 Setup Script v1.0       "
echo "=================================================="

# 1. Update packages
echo "[1/8] Updating system packages..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

# 2. Install system tools
echo "[2/8] Installing system tools..."
sudo apt-get install -y -qq \
    git \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    iperf \
    iperf3 \
    iproute2 \
    iptables \
    mtr-tiny \
    dnsutils \
    ntp \
    ntpdate \
    htop \
    net-tools

# 3. Install Docker
echo "[3/8] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "[Docker] Installed. You may need to log out and back in."
else
    echo "[Docker] Already installed. Skipping."
fi

# Install Docker Compose plugin
sudo apt-get install -y -qq docker-compose-plugin || true

# 4. Configure NTP (Pi acts as local NTP server for ESP32 probes)
echo "[4/8] Configuring NTP server..."
sudo tee /etc/ntp.conf > /dev/null <<'NTP_CONF'
# Trinetra NTP Configuration
# Sync to public servers
server 0.in.pool.ntp.org iburst
server 1.in.pool.ntp.org iburst
server 2.in.pool.ntp.org iburst
server 3.in.pool.ntp.org iburst

# Allow LAN devices (ESP32 probes) to sync from this Pi
restrict 192.168.0.0 mask 255.255.0.0 nomodify notrap

driftfile /var/lib/ntp/drift
NTP_CONF
sudo systemctl enable ntp
sudo systemctl restart ntp

# 5. Install Python dependencies
echo "[5/8] Installing Python dependencies..."
pip3 install --break-system-packages \
    paho-mqtt \
    influxdb-client \
    pandas \
    numpy \
    scikit-learn \
    xgboost \
    matplotlib \
    seaborn \
    requests

# 6. Configure iptables persistence (for fault_injector.py cleanup on reboot)
echo "[6/8] Configuring iptables persistence..."
sudo apt-get install -y -qq iptables-persistent || true

# 7. Enable IP forwarding (needed for tc netem on eth0)
echo "[7/8] Enabling IP forwarding..."
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p > /dev/null

# 8. Start Trinetra Docker stack
echo "[8/8] Starting Trinetra Docker services..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(dirname "$SCRIPT_DIR")/config"

if [ -f "$CONFIG_DIR/docker-compose.yml" ]; then
    cd "$CONFIG_DIR"
    sudo docker compose up -d
    echo "[Docker] Services started."
else
    echo "[Warning] docker-compose.yml not found at $CONFIG_DIR"
    echo "Run: cd config && docker compose up -d"
fi

echo ""
echo "=================================================="
echo "   Trinetra Setup Complete!"
echo ""
echo "   Next Steps:"
echo "   1. Start wired baseline:"
echo "      python3 pi_scripts/wan_probe.py"
echo ""
echo "   2. Open Trinetra dashboard:"
echo "      http://$(hostname -I | awk '{print $1}'):8888"
echo "   3. Open Grafana (optional):"
echo "      http://$(hostname -I | awk '{print $1}'):3000"
echo ""
echo "   4. Flash ESP32 firmware:"
echo "      See firmware/esp32_probe/esp32_probe.ino"
echo "      Set MQTT_BROKER to: $(hostname -I | awk '{print $1}')"
echo "=================================================="
