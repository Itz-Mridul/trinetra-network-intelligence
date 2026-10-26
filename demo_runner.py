#!/usr/bin/env python3
"""
Trinetra - Prototype Interactive Demo Runner
Designed for live project reviews and supervisor demonstrations.
Can run in two modes:
  1. Real Hardware Mode: Reads live MQTT from Pi and ESP32s and displays real-time diagnosis.
  2. Simulation Mode: Simulates 1 Pi and 2 ESP32 probes with controllable fault injection
     so you can demo the full Grafana dashboard and classifier even before all boards are soldered.
"""

import os
import sys
import time
import json
import random
import threading
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

# Import local classifier
sys.path.append(os.path.join(os.path.dirname(__file__), "analysis"))
try:
    from classify_rules import classify_window
except ImportError:
    print("[Error] classify_rules.py not found in analysis/")
    sys.exit(1)

MQTT_BROKER = os.getenv("PIPROBE_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("PIPROBE_MQTT_PORT", 1883))

# Global demo state
current_fault = "normal"
run_counter = 1
running = True

def get_simulated_metrics(fault):
    """Generate realistic telemetry based on active ground truth."""
    # Normal baseline
    pi = {
        "gw_rtt_mean_ms": round(random.uniform(1.1, 1.8), 2),
        "gw_loss_pct": 0.0,
        "inet_rtt_mean_ms": round(random.uniform(12.0, 16.5), 2),
        "inet_loss_pct": 0.0,
        "dns_latency_ms": round(random.uniform(15.0, 28.0), 1),
        "http_ttfb_ms": round(random.uniform(50.0, 75.0), 1)
    }
    esp1 = {
        "probe_id": "esp_probe_1",
        "room_id": "R1_living_room",
        "rssi_raw_dbm": random.randint(-62, -58),
        "rssi_calibrated_dbm": random.randint(-62, -58) + 1.2,
        "gw_rtt_mean_ms": round(random.uniform(4.5, 7.2), 2),
        "gw_rtt_jitter_ms": round(random.uniform(1.0, 2.5), 2),
        "gw_loss_pct": 0.0,
        "ap_count_on_channel": 4,
        "reconnect_count": 0
    }
    esp2 = {
        "probe_id": "esp_probe_2",
        "room_id": "R2_bedroom",
        "rssi_raw_dbm": random.randint(-68, -64),
        "rssi_calibrated_dbm": random.randint(-68, -64) - 0.8,
        "gw_rtt_mean_ms": round(random.uniform(5.5, 8.5), 2),
        "gw_rtt_jitter_ms": round(random.uniform(1.2, 3.0), 2),
        "gw_loss_pct": 0.0,
        "ap_count_on_channel": 4,
        "reconnect_count": 0
    }

    # Impairments
    if fault == "wan_degraded":
        pi["inet_rtt_mean_ms"] = round(random.uniform(210.0, 260.0), 1)
        pi["inet_loss_pct"] = round(random.uniform(4.0, 8.0), 1)
        pi["http_ttfb_ms"] = round(random.uniform(280.0, 390.0), 1)
        # Wi-Fi probes still have great local latency, but external is high
        esp1["gw_rtt_mean_ms"] = round(random.uniform(5.0, 8.0), 2)
    elif fault == "dns_fail":
        pi["dns_latency_ms"] = -1.0  # Timeout
        pi["http_ttfb_ms"] = -1.0
    elif fault == "coverage_weak":
        esp2["rssi_raw_dbm"] = random.randint(-84, -79)
        esp2["rssi_calibrated_dbm"] = esp2["rssi_raw_dbm"] - 0.8
        esp2["gw_rtt_mean_ms"] = round(random.uniform(45.0, 85.0), 1)
        esp2["gw_rtt_jitter_ms"] = round(random.uniform(25.0, 40.0), 1)
        esp2["gw_loss_pct"] = round(random.uniform(5.0, 15.0), 1)
    elif fault == "interference":
        # WiSlow signature: RSSI is good (-60dBm), but loss and jitter spike due to channel contention
        esp1["rssi_raw_dbm"] = random.randint(-63, -59)
        esp1["rssi_calibrated_dbm"] = esp1["rssi_raw_dbm"] + 1.2
        esp1["gw_loss_pct"] = round(random.uniform(6.0, 12.0), 1)
        esp1["gw_rtt_jitter_ms"] = round(random.uniform(18.0, 35.0), 1)
        esp1["ap_count_on_channel"] = 7
    elif fault == "ap_overload":
        esp1["gw_rtt_mean_ms"] = round(random.uniform(22.0, 38.0), 1)
        esp2["gw_rtt_mean_ms"] = round(random.uniform(25.0, 42.0), 1)

    return pi, [esp1, esp2]

def publisher_loop():
    """Background publisher to MQTT for live Grafana demo."""
    global running, current_fault, run_counter
    if not HAS_MQTT:
        print("[Note] paho-mqtt not installed locally; running in local CLI diagnostic mode.")
        return

    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"[Warning] Could not connect to MQTT broker ({e}). Simulation will run locally.")

    while running:
        pi, wifi_list = get_simulated_metrics(current_fault)
        run_id = f"demo_run_{run_counter}"

        # Publish Pi
        pi_payload = {
            "timestamp": time.time(),
            "probe_id": "pi5_gateway",
            "layer": "wan",
            "room_id": "server_corner",
            "gw_rtt_mean_ms": pi["gw_rtt_mean_ms"],
            "gw_loss_pct": pi["gw_loss_pct"],
            "inet_rtt_mean_ms": pi["inet_rtt_mean_ms"],
            "inet_loss_pct": pi["inet_loss_pct"],
            "dns_latency_ms": pi["dns_latency_ms"],
            "http_ttfb_ms": pi["http_ttfb_ms"],
            "fault_class": current_fault,
            "run_id": run_id
        }
        try:
            client.publish("piprobe/pi/wan", json.dumps(pi_payload))
        except Exception:
            pass

        # Publish ESP32s
        for esp in wifi_list:
            esp_payload = {
                "timestamp": time.time(),
                "probe_id": esp["probe_id"],
                "layer": "wifi",
                "room_id": esp["room_id"],
                "rssi_raw_dbm": esp["rssi_raw_dbm"],
                "rssi_calibrated_dbm": esp["rssi_calibrated_dbm"],
                "gw_rtt_mean_ms": esp["gw_rtt_mean_ms"],
                "gw_rtt_jitter_ms": esp["gw_rtt_jitter_ms"],
                "gw_loss_pct": esp["gw_loss_pct"],
                "ap_count_on_channel": esp["ap_count_on_channel"],
                "fault_class": current_fault,
                "run_id": run_id
            }
            try:
                client.publish(f"piprobe/{esp['probe_id']}/wifi", json.dumps(esp_payload))
            except Exception:
                pass

        time.sleep(3.0)

def main():
    global current_fault, running, run_counter
    print("=================================================================")
    print("        Trinetra Interactive Prototype Demo Runner               ")
    print("=================================================================")
    print("Publishing live telemetry to MQTT for Grafana in the background...")

    pub_thread = threading.Thread(target=publisher_loop, daemon=True)
    pub_thread.start()

    menu = """
Select Action / Inject Fault:
  [0] F0: Normal Operation (All KPIs healthy)
  [1] F1: WAN / ISP Degradation (tc netem simulation)
  [2] F3: DNS Resolver Failure
  [3] F5: Wi-Fi Coverage Hole (Bedroom probe attenuated)
  [4] F6: Co-channel Interference (WiSlow condition: good RSSI, high loss)
  [5] F7: Access Point Overload
  [d] Run Live Cross-Layer Diagnosis Now
  [q] Quit Demo
Choice > """

    while True:
        try:
            choice = input(menu).strip().lower()
            if choice == "0":
                current_fault = "normal"
                print("\n--> INJECTED: F0 (Normal Operation)")
            elif choice == "1":
                current_fault = "wan_degraded"
                print("\n--> INJECTED: F1 (WAN / ISP Degradation)")
            elif choice == "2":
                current_fault = "dns_fail"
                print("\n--> INJECTED: F3 (DNS Resolver Failure)")
            elif choice == "3":
                current_fault = "coverage_weak"
                print("\n--> INJECTED: F5 (Wi-Fi Coverage Hole)")
            elif choice == "4":
                current_fault = "interference"
                print("\n--> INJECTED: F6 (Co-channel Interference)")
            elif choice == "5":
                current_fault = "ap_overload"
                print("\n--> INJECTED: F7 (Access Point Overload)")
            elif choice == "d":
                pi, wifi_list = get_simulated_metrics(current_fault)
                verdict, conf, reasons = classify_window(pi, wifi_list)
                print("\n" + "=" * 50)
                print(f"LIVE CLASSIFIER OUTPUT:")
                print(f"  Ground Truth   : {current_fault.upper()}")
                print(f"  Predicted Cause: {verdict.upper()}")
                print(f"  Confidence     : {conf.upper()}")
                print(f"  Key Evidence   :")
                for r in reasons:
                    print(f"    - {r}")
                print("=" * 50 + "\n")
            elif choice == "q":
                running = False
                print("Exiting demo runner.")
                break
        except (KeyboardInterrupt, EOFError):
            running = False
            break

if __name__ == "__main__":
    main()
