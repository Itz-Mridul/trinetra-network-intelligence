#!/usr/bin/env python3
"""
Trinetra WAN evidence collector.

The collector separates the local hotspot path from the outside Internet
path.  ICMP is retained as a diagnostic signal, but the WAN verdict is based
on several HTTPS targets and an optional small download test so that one
blocked ping target cannot be mistaken for an ISP outage.
"""

import os
import sys
import time
import json
import socket
import subprocess
import urllib.request
from statistics import median
import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("PIPROBE_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("PIPROBE_MQTT_PORT", 1883))
MQTT_TOPIC = "piprobe/pi/wan"
PROBE_ID = os.getenv("PIPROBE_ID", "pi5_gateway")
SELECTED_CARRIER = os.getenv("PIPROBE_CARRIER", "")
ROOM_ID = os.getenv("PIPROBE_ROOM", "server_corner")
SITE_ID = os.getenv("PIPROBE_SITE_ID", "unassigned_site")
SESSION_ID = os.getenv("PIPROBE_SESSION_ID", "")
LOCATION_ID = os.getenv("PIPROBE_LOCATION_ID", ROOM_ID)
INTERVAL_SEC = int(os.getenv("PIPROBE_INTERVAL", 10))
HTTPS_TARGETS = tuple(filter(None, os.getenv(
    "PIPROBE_HTTPS_TARGETS",
    "https://www.google.com/generate_204,https://www.cloudflare.com/cdn-cgi/trace,https://example.com"
).split(",")))
DOWNLOAD_URL = os.getenv(
    "PIPROBE_DOWNLOAD_URL",
    "https://speed.cloudflare.com/__down?bytes=1000000"
)
THROUGHPUT_INTERVAL_SEC = int(os.getenv("PIPROBE_THROUGHPUT_INTERVAL", 60))
DOWNLOAD_MAX_BYTES = int(os.getenv("PIPROBE_DOWNLOAD_MAX_BYTES", 1000000))
STATE_FILE = "/tmp/piprobe_fault_state.json"


def get_network_identity():
    """Return local router/interface identity and public-IP geolocation evidence."""
    interface = ""
    local_ip = ""
    gateway_ip = get_default_gateway()
    router_mac = ""
    wifi_ssid = ""
    try:
        route = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2).stdout
        parts = route.strip().split()
        if "dev" in parts:
            interface = parts[parts.index("dev") + 1]
        if interface:
            addresses = subprocess.run(["ip", "-o", "-4", "addr", "show", "dev", interface], capture_output=True, text=True, timeout=2).stdout
            for token in addresses.split():
                if "/" in token and token.count(".") == 3:
                    local_ip = token.split("/")[0]
                    break
            neighbor = subprocess.run(["ip", "neigh", "show", gateway_ip], capture_output=True, text=True, timeout=2).stdout.split()
            if "lladdr" in neighbor:
                router_mac = neighbor[neighbor.index("lladdr") + 1]
    except Exception:
        pass
    try:
        wifi_ssid = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:
        pass

    identity = {
        "local_ip": local_ip,
        "gateway_ip": gateway_ip,
        "interface_name": interface,
        "router_mac": router_mac,
        "wifi_ssid": wifi_ssid,
    }
    try:
        request = urllib.request.Request("https://ipinfo.io/json", headers={"User-Agent": "Trinetra/1.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            public = json.loads(response.read().decode())
        identity.update({
            "public_ip": public.get("ip", ""),
            "isp_org": public.get("org", ""),
            "isp_asn": public.get("org", "").split(" ", 1)[0] if public.get("org") else "",
            "public_city": public.get("city", ""),
            "public_region": public.get("region", ""),
            "public_country": public.get("country", ""),
            "public_timezone": public.get("timezone", ""),
        })
        loc = str(public.get("loc", "")).split(",")
        if len(loc) == 2:
            identity["public_latitude"] = float(loc[0])
            identity["public_longitude"] = float(loc[1])
    except Exception:
        pass
    return identity

def get_default_gateway():
    """Extract default gateway IP from routing table."""
    try:
        res = subprocess.run(["ip", "route", "show", "default"],
                             capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout:
            parts = res.stdout.strip().split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    except Exception:
        pass
    # Fallback for macOS / testing
    try:
        res = subprocess.run(["route", "-n", "get", "default"],
                             capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            if "gateway:" in line:
                return line.split(":")[1].strip()
    except Exception:
        pass
    return "192.168.1.1"

def ping_stats(target, count=5):
    """Run ping and return (mean_ms, stddev_ms, loss_pct)."""
    try:
        # Determine platform-specific ping arg (-c 5 on Linux/macOS)
        res = subprocess.run(
            ["ping", "-c", str(count), "-W", "1", target],
            capture_output=True, text=True, timeout=count + 2
        )
        output = res.stdout
        loss_pct = 100.0
        mean_ms = -1.0
        stddev_ms = 0.0

        for line in output.splitlines():
            if "packet loss" in line:
                # Example: 5 packets transmitted, 5 received, 0% packet loss
                parts = line.split(",")
                for p in parts:
                    if "%" in p:
                        loss_pct = float(p.split("%")[0].strip().split()[-1])
            if "rtt min/avg/max/mdev" in line or "round-trip min/avg/max/stddev" in line:
                # Example: rtt min/avg/max/mdev = 1.2/2.1/3.4/0.5 ms
                stats = line.split("=")[1].strip().split()[0].split("/")
                mean_ms = float(stats[1])
                stddev_ms = float(stats[3])

        return mean_ms, stddev_ms, loss_pct
    except Exception:
        return -1.0, 0.0, 100.0

def measure_dns(domain="google.com"):
    """Measure DNS resolution time in ms."""
    t0 = time.perf_counter()
    try:
        socket.getaddrinfo(domain, 80)
        return round((time.perf_counter() - t0) * 1000.0, 2)
    except Exception:
        return -1.0

def measure_http(url):
    """Return one HTTPS target's TTFB in milliseconds, or -1 on failure."""
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Trinetra/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read(64)
            return round((time.perf_counter() - t0) * 1000.0, 2)
    except Exception:
        return -1.0


def measure_https_targets(targets):
    """Measure multiple HTTPS targets and return median TTFB and success rate."""
    samples = [measure_http(url) for url in targets]
    good = [value for value in samples if value >= 0]
    return (
        round(median(good), 2) if good else -1.0,
        round((len(good) / len(samples)) * 100.0, 1) if samples else 0.0,
        len(good),
        len(samples),
    )


def measure_download(url, max_bytes=1000000):
    """Measure a bounded HTTPS download in Mbps; return -1 when unavailable."""
    if not url:
        return -1.0, 0
    started = time.perf_counter()
    received = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Trinetra/1.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            while received < max_bytes:
                chunk = response.read(min(65536, max_bytes - received))
                if not chunk:
                    break
                received += len(chunk)
        elapsed = time.perf_counter() - started
        if received == 0 or elapsed <= 0:
            return -1.0, received
        return round((received * 8.0 / elapsed) / 1_000_000.0, 3), received
    except Exception:
        return -1.0, received

def get_system_metrics():
    """Retrieve Pi CPU temperature and memory usage."""
    temp_c = 0.0
    mem_pct = 0.0
    # Linux thermal zone
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_c = round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        temp_c = 40.0

    # Memory info
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            mem_total = 1
            mem_avail = 1
            for l in lines:
                if l.startswith("MemTotal:"):
                    mem_total = int(l.split()[1])
                elif l.startswith("MemAvailable:"):
                    mem_avail = int(l.split()[1])
            mem_pct = round(((mem_total - mem_avail) / mem_total) * 100.0, 1)
    except Exception:
        mem_pct = 25.0

    return temp_c, mem_pct

def read_fault_state():
    """Read dynamic ground-truth fault tag injected by fault_injector.py."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"fault_class": "normal", "run_id": "run_baseline", "split": "train"}

def main():
    gateway_ip = get_default_gateway()
    session_id = SESSION_ID or f"session_{int(time.time())}"
    print(f"[Trinetra WAN Baseline] Initializing... Gateway: {gateway_ip}")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        print(f"[Trinetra WAN Baseline] Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        print(f"[Trinetra WAN Baseline] Warning: MQTT connect failed ({e}). Will retry inline.")

    last_throughput_at = 0.0
    download_mbps = -1.0
    download_bytes = 0
    identity = get_network_identity()
    last_identity_at = time.time()

    while True:
        cycle_start = time.time()
        state = read_fault_state()

        if cycle_start - last_identity_at >= 300:
            identity = get_network_identity()
            last_identity_at = cycle_start

        gw_mean, gw_std, gw_loss = ping_stats(gateway_ip, count=4)
        inet_mean, inet_std, inet_loss = ping_stats("8.8.8.8", count=4)
        dns_lat = measure_dns("cloudflare.com")
        http_ttfb, https_success, https_success_count, https_target_count = measure_https_targets(HTTPS_TARGETS)
        if cycle_start - last_throughput_at >= THROUGHPUT_INTERVAL_SEC:
            download_mbps, download_bytes = measure_download(DOWNLOAD_URL, DOWNLOAD_MAX_BYTES)
            last_throughput_at = cycle_start
        cpu_t, mem_u = get_system_metrics()

        payload = {
            "timestamp": round(cycle_start, 3),
            "probe_id": PROBE_ID,
            "site_id": SITE_ID,
            "session_id": session_id,
            "layer": "wan",
            "room_id": ROOM_ID,
            "location_id": LOCATION_ID,
            "carrier_name": SELECTED_CARRIER or None,
            **identity,
            "gw_rtt_mean_ms": gw_mean,
            "gw_rtt_std_ms": gw_std,
            "gw_loss_pct": gw_loss,
            "inet_rtt_mean_ms": inet_mean,
            "inet_rtt_std_ms": inet_std,
            "inet_loss_pct": inet_loss,
            "dns_latency_ms": dns_lat,
            "http_ttfb_ms": http_ttfb,
            "wan_http_success_pct": https_success,
            "wan_http_success_count": https_success_count,
            "wan_http_target_count": https_target_count,
            "wan_tput_dl_mbps": download_mbps,
            "wan_tput_dl_bytes": download_bytes,
            "cpu_temp_c": cpu_t,
            "mem_used_pct": mem_u,
            "fault_class": state.get("fault_class", "normal"),
            "run_id": state.get("run_id", "run_baseline"),
            "split": state.get("split", "train")
        }

        # Ensure MQTT is connected before publishing
        if not client.is_connected():
            try:
                client.reconnect()
                print(f"[Trinetra WAN Baseline] Reconnected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            except Exception:
                try:
                    client.connect(MQTT_BROKER, MQTT_PORT, 60)
                    client.loop_start()
                    print(f"[Trinetra WAN Baseline] Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
                except Exception as ce:
                    print(f"[Trinetra WAN Baseline] MQTT reconnect failed: {ce}")

        try:
            client.publish(MQTT_TOPIC, json.dumps(payload), qos=0)
            print(
                f"[{payload['fault_class']}] gw={gw_mean}ms, inet={inet_mean}ms, "
                f"https={https_success}%, ttfb={http_ttfb}ms, "
                f"download={download_mbps}Mbps, loss={inet_loss}%"
            )
        except Exception as e:
            print(f"Publish error: {e}")

        elapsed = time.time() - cycle_start
        sleep_dur = max(0.5, INTERVAL_SEC - elapsed)
        time.sleep(sleep_dur)

if __name__ == "__main__":
    main()
