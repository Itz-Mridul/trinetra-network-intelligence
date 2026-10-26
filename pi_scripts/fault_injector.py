#!/usr/bin/env python3
"""
Trinetra - Controlled Fault-Injection Testbed Engine
Automates controlled network impairments, ground-truth tagging, and tear-down.
Injects:
  - F0: normal (baseline)
  - F1: wan_degraded (tc netem delay 200ms +/- 50ms, loss 5%)
  - F2: wan_down (iptables block external internet transit)
  - F3: dns_fail (iptables block port 53 UDP/TCP)
  - F6: interference (iperf2 UDP channel flood to induce contention)

Coordinates ground-truth tags with:
  1. /tmp/piprobe_fault_state.json (read by local wan_probe.py)
  2. piprobe/control/state (MQTT broadcast to all active ESP32 probes)
Logs all runs to data/injection_log.csv
"""

import os
import sys
import time
import json
import signal
import argparse
import subprocess
import paho.mqtt.client as mqtt

STATE_FILE = "/tmp/piprobe_fault_state.json"
LOG_FILE = os.path.join(os.path.dirname(__file__), "../data/injection_log.csv")
INTERFACE = os.getenv("PIPROBE_IFACE", "eth0")
MQTT_BROKER = os.getenv("PIPROBE_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("PIPROBE_MQTT_PORT", 1883))

ACTIVE_RULES = []

def run_cmd(cmd):
    """Execute system command safely."""
    print(f"[CMD] {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)

def update_state(fault_class, run_id, split="train", params=None):
    """Write state to disk and publish via MQTT."""
    state = {
        "fault_class": fault_class,
        "run_id": run_id,
        "split": split,
        "timestamp": time.time(),
        "params": params or {}
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    # Broadcast via MQTT
    try:
        client = mqtt.Client()
        client.connect(MQTT_BROKER, MQTT_PORT, 5)
        client.publish("piprobe/control/state", json.dumps(state), retain=True)
        client.disconnect()
    except Exception as e:
        print(f"[MQTT] Note: could not broadcast state ({e})")

def cleanup_all():
    """Tear down any active tc netem or iptables rules."""
    print("\n[CLEANUP] Reverting all injected network impairments...")
    # Clean tc netem
    run_cmd(["sudo", "tc", "qdisc", "del", "dev", INTERFACE, "root"])

    # Clean iptables rules
    run_cmd(["sudo", "iptables", "-D", "OUTPUT", "-p", "udp", "--dport", "53", "-j", "DROP"])
    run_cmd(["sudo", "iptables", "-D", "OUTPUT", "-p", "tcp", "--dport", "53", "-j", "DROP"])
    run_cmd(["sudo", "iptables", "-D", "OUTPUT", "-d", "8.8.8.8", "-j", "DROP"])
    run_cmd(["sudo", "iptables", "-D", "OUTPUT", "-d", "1.1.1.1", "-j", "DROP"])

    # Reset state to normal
    update_state("normal", "baseline_idle", "train")
    print("[CLEANUP] Network restored to normal baseline.")

def inject_f1_wan_degraded(delay_ms=200, jitter_ms=50, loss_pct=5):
    """F1: WAN degradation via tc netem."""
    print(f"[INJECT] F1: Adding {delay_ms}ms (+/-{jitter_ms}ms) delay and {loss_pct}% loss on {INTERFACE}...")
    run_cmd(["sudo", "tc", "qdisc", "del", "dev", INTERFACE, "root"])
    res = run_cmd([
        "sudo", "tc", "qdisc", "add", "dev", INTERFACE, "root", "netem",
        "delay", f"{delay_ms}ms", f"{jitter_ms}ms", "loss", f"{loss_pct}%"
    ])
    if res.returncode != 0:
        print(f"[ERROR] tc netem failed (code {res.returncode}): {res.stderr.strip()}")
        return False
    return True

def inject_f2_wan_down():
    """F2: Router WAN uplink disconnection (simulated by dropping public internet transit)."""
    print("[INJECT] F2: Dropping public internet traffic (gateway stays reachable)...")
    res1 = run_cmd(["sudo", "iptables", "-A", "OUTPUT", "-d", "8.8.8.8", "-j", "DROP"])
    res2 = run_cmd(["sudo", "iptables", "-A", "OUTPUT", "-d", "1.1.1.1", "-j", "DROP"])
    if res1.returncode != 0 or res2.returncode != 0:
        print(f"[ERROR] iptables failed to drop WAN transit (code {res1.returncode}/{res2.returncode})")
        return False
    return True

def inject_f3_dns_fail():
    """F3: DNS server unreachable (drop all port 53 traffic)."""
    print("[INJECT] F3: Blocking port 53 UDP/TCP...")
    res1 = run_cmd(["sudo", "iptables", "-A", "OUTPUT", "-p", "udp", "--dport", "53", "-j", "DROP"])
    res2 = run_cmd(["sudo", "iptables", "-A", "OUTPUT", "-p", "tcp", "--dport", "53", "-j", "DROP"])
    if res1.returncode != 0 or res2.returncode != 0:
        print(f"[ERROR] iptables failed to block DNS traffic (code {res1.returncode}/{res2.returncode})")
        return False
    return True

def inject_f5_interference(delay_ms=45, jitter_ms=30, loss_pct=8, corrupt_pct=3):
    """F5: Wi-Fi co-channel interference & collision emulation."""
    print(f"[INJECT] F5: Simulating Wi-Fi RF interference ({delay_ms}ms jitter, {loss_pct}% loss, {corrupt_pct}% corrupt)...")
    run_cmd(["sudo", "tc", "qdisc", "del", "dev", INTERFACE, "root"])
    res = run_cmd([
        "sudo", "tc", "qdisc", "add", "dev", INTERFACE, "root", "netem",
        "delay", f"{delay_ms}ms", f"{jitter_ms}ms", "loss", f"{loss_pct}%", "corrupt", f"{corrupt_pct}%"
    ])
    if res.returncode != 0:
        print(f"[ERROR] tc netem interference rule failed: {res.stderr.strip()}")
        return False
    return True

def inject_f6_ap_overload(queue_delay_ms=90, loss_pct=6, rate_limit="1500kbit"):
    """F6: Access Point bufferbloat & bottleneck queue overload."""
    print(f"[INJECT] F6: Simulating AP bufferbloat & overload ({queue_delay_ms}ms delay, {loss_pct}% loss, rate {rate_limit})...")
    run_cmd(["sudo", "tc", "qdisc", "del", "dev", INTERFACE, "root"])
    res = run_cmd([
        "sudo", "tc", "qdisc", "add", "dev", INTERFACE, "root", "netem",
        "delay", f"{queue_delay_ms}ms", "20ms", "loss", f"{loss_pct}%", "rate", rate_limit
    ])
    if res.returncode != 0:
        print(f"[ERROR] tc netem AP overload rule failed: {res.stderr.strip()}")
        return False
    return True

def log_experiment(run_id, fault_class, start_t, end_t, split, params):
    """Append trial metadata to data/injection_log.csv."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a") as f:
        if not file_exists:
            f.write("run_id,fault_class,start_ts,end_ts,duration_sec,split,parameters\n")
        dur = round(end_t - start_t, 2)
        param_str = json.dumps(params).replace(",", ";")
        f.write(f"{run_id},{fault_class},{round(start_t, 3)},{round(end_t, 3)},{dur},{split},{param_str}\n")
    print(f"[LOG] Logged trial {run_id} ({fault_class}) to {LOG_FILE}")

def run_trial(fault_class, duration_sec, split="train", params=None):
    """Execute a single controlled trial with automatic cleanup."""
    run_id = f"run_{int(time.time())}_{fault_class}"
    print(f"\n=======================================================")
    print(f"Starting Trial: {run_id} | Class: {fault_class} | Duration: {duration_sec}s")
    print(f"=======================================================")

    cleanup_all()
    params = params or {}
    start_t = time.time()

    success = True
    if fault_class == "normal":
        print("[INJECT] F0: Normal operating baseline. No impairment active.")
    elif fault_class == "wan_degraded":
        success = inject_f1_wan_degraded()
    elif fault_class == "wan_down":
        success = inject_f2_wan_down()
    elif fault_class == "dns_fail":
        success = inject_f3_dns_fail()
    elif fault_class == "interference":
        success = inject_f5_interference()
    elif fault_class == "ap_overload":
        success = inject_f6_ap_overload()
    elif fault_class == "coverage_weak":
        print("[ACTION REQUIRED] Move probe to dead zone or insert shielded box now.")
    else:
        print(f"[WARNING] Manual fault class '{fault_class}'. Tagging only.")

    if not success:
        print(f"[CRITICAL ERROR] Fault injection failed to apply for {fault_class}! Aborting trial to avoid corrupted training data.")
        cleanup_all()
        return

    update_state(fault_class, run_id, split, params)

    try:
        # Progress countdown
        for remaining in range(duration_sec, 0, -5):
            print(f"  [{fault_class}] {remaining}s remaining...")
            time.sleep(min(5, remaining))
    except KeyboardInterrupt:
        print("\n[ABORT] Trial interrupted by user.")
    finally:
        end_t = time.time()
        cleanup_all()
        log_experiment(run_id, fault_class, start_t, end_t, split, params)

def main():
    parser = argparse.ArgumentParser(description="Trinetra Controlled Fault Injector")
    parser.add_argument("--fault", choices=["normal", "wan_degraded", "wan_down", "dns_fail", "coverage_weak", "interference", "ap_overload"],
                        default="wan_degraded", help="Fault class to inject")
    parser.add_argument("--duration", type=int, default=180, help="Duration in seconds (default: 180s = 3 mins)")
    parser.add_argument("--split", choices=["train", "test_time", "test_room", "test_board"], default="train", help="Dataset split tag")
    parser.add_argument("--cleanup", action="store_true", help="Clean up any active network rules and exit")
    args = parser.parse_args()

    # Handle graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, lambda sig, frame: (cleanup_all(), sys.exit(0)))

    if args.cleanup:
        cleanup_all()
        return

    run_trial(args.fault, args.duration, args.split)

if __name__ == "__main__":
    main()
