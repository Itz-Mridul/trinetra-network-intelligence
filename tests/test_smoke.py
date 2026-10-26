"""Dependency-free project smoke checks.

These checks validate the files and contracts that can be tested without
hardware, Docker, MQTT, or InfluxDB.
"""
from pathlib import Path
import ast
import configparser
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def check_files():
    required = [
        "dashboard/index.html",
        "dashboard/server.py",
        "dashboard/Dockerfile",
        "firmware/esp32_probe/esp32_probe.ino",
        "firmware/esp32_probe/config.example.h",
        "pi_scripts/mqtt_to_influx.py",
        "pi_scripts/wan_probe.py",
        "phone/termux_sender.sh",
        "pi_scripts/piprobe-wan.service",
        "config/docker-compose.yml",
        "config/telegraf.conf",
    ]
    missing = [p for p in required if not (ROOT / p).is_file()]
    assert not missing, f"missing required files: {missing}"


def check_python():
    for path in list((ROOT / "analysis").glob("*.py")) + list((ROOT / "pi_scripts").glob("*.py")) + [ROOT / "dashboard/server.py"]:
        ast.parse(path.read_text(), filename=str(path))


def check_deployment_contract():
    compose = (ROOT / "config/docker-compose.yml").read_text()
    assert compose.count("services:") == 1
    for service in ("mosquitto:", "influxdb:", "telegraf:", "grafana:", "dashboard:"):
        assert service in compose, f"missing compose service: {service}"
    assert "influxdb:1.8" in compose
    assert "8888:8888" in compose
    assert "context: ../dashboard" in compose
    assert "influxdb2" not in compose

    server = (ROOT / "dashboard/server.py").read_text()
    assert "/api/influx/query" in server
    assert 'INFLUX_HOST = os.getenv("INFLUX_HOST", "127.0.0.1")' in server

    installer = (ROOT / "pi_scripts/install_service.sh").read_text()
    assert 'SERVICE_SRC="$PIPROBE_DIR/pi_scripts/piprobe-wan.service"' in installer

    wan = (ROOT / "pi_scripts/wan_probe.py").read_text()
    assert "measure_https_targets" in wan
    assert "wan_tput_dl_mbps" in wan
    assert "PIPROBE_HTTPS_TARGETS" in wan
    assert '"carrier_name": SELECTED_CARRIER or None' in wan


def check_no_local_secret():
    path = ROOT / "firmware/esp32_probe/config.h"
    if not path.exists():
        return
    config = path.read_text()
    assert 'WIFI_PASSWORD     "123456789"' not in config
    assert 'WIFI_SSID         "Le Bikhari"' not in config


def check_model_artifact():
    summary_path = ROOT / "data/figures/eval_summary.json"
    model_path = ROOT / "data/models/best_model.pkl"
    if not summary_path.exists() or not model_path.exists():
        return
    summary = json.loads(summary_path.read_text())
    assert "accuracy" in summary
    assert model_path.stat().st_size > 0


if __name__ == "__main__":
    for check in (check_files, check_python, check_deployment_contract, check_no_local_secret, check_model_artifact):
        check()
        print(f"PASS {check.__name__}")
