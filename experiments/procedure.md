# Trinetra Experiment Procedure
## Reproducible Step-by-Step Protocol for IEEE Publication

Version: 1.0 | Date: October 2026

---

## Hardware Setup (One-Time)

### Step 1: Raspberry Pi 5 — Central Hub
1. Flash **Raspberry Pi OS 64-bit Lite** using Raspberry Pi Imager.
2. Enable SSH: place empty file named `ssh` in boot partition.
3. Boot and connect via SSH.
4. Connect **Ethernet cable** from Pi to router LAN port. Verify: `ip addr show eth0`.
5. Clone the project: `git clone <repo_url> ~/piprobe`
6. Run setup: `bash ~/piprobe/pi_scripts/setup_pi.sh`
7. Note the Pi's IP address: `hostname -I | awk '{print $1}'`

### Step 2: ESP32 Probes — Wireless Sensors
For each ESP32 board:
1. Open `firmware/esp32_probe/esp32_probe.ino` in Arduino IDE.
2. Set these constants:
   ```cpp
   const char* WIFI_SSID     = "YOUR_SSID";
   const char* WIFI_PASSWORD = "YOUR_PASSWORD";
   const char* MQTT_BROKER   = "192.168.X.X"; // Pi IP
   #define PROBE_ID  "esp_probe_1"  // Unique per board
   #define ROOM_ID   "R1_living_room"
   #define CALIBRATION_BIAS  0.0  // Set after calibration experiment
   ```
3. Flash: Connect via USB → Arduino IDE → Upload.
4. Open Serial Monitor (115200 baud) — verify telemetry messages appear.
5. Label each physical board: attach a sticker with its `PROBE_ID`.

### Step 3: Floor Plan Preparation
1. Sketch or photograph the floor plan of the test building.
2. Mark room IDs: **R1** (near AP), **R2** (mid-range), **R3** (far corner), etc.
3. Mark the router/AP location.
4. Mark the Pi location (server corner, Ethernet-connected).

---

## Phase 1: Calibration Experiments (Day 2)

### Experiment C1: Board-to-Board Co-location Test
**Goal:** Measure inter-board RSSI systematic bias.
1. Place all 3 ESP32 boards side-by-side (within 5 cm), same orientation (vertical, antenna up).
2. Collect data for **10 minutes** at fixed location (middle of R1, 1 m from AP).
3. Verify data in InfluxDB: all 3 probes, same `room_id = "calibration_colocate"`.
4. Run: `python3 analysis/calibration.py --csv data/calibration/cal_data.csv`
5. Record `calibration_bias_dbm` for each board.
6. **Update firmware** with bias values and reflash each probe.

### Experiment C2: Antenna Orientation Test
1. Fix one probe at the calibration location.
2. Test 5 orientations: 0°, 45°, 90°, 135°, 180° — 5 minutes each.
3. Tag session with `orientation_deg` in InfluxDB or CSV.
4. Run calibration.py to extract orientation_analysis results.
5. **Decision:** Select the best single orientation. Mount all probes at this angle for all subsequent experiments.

### Experiment C3: Temporal Variance (Noise Floor)
1. Fix one probe in R1.
2. Collect 3 sessions: morning, afternoon, evening (20 min each, no fault injection).
3. Tag `session_id = "temporal_test"`.
4. This gives the noise floor — fault-induced deltas must exceed this.

---

## Phase 2: Baseline Data Collection (Day 3)

### Experiment B1: Multi-Room Normal Baseline
1. Place probes in their permanent rooms (R1, R2, R3).
2. Start all daemons and Docker stack.
3. Collect **2 hours of normal operation** with no fault injection.
4. Verify in Grafana: all probes appear, data is continuous.

---

## Phase 3: Controlled Fault Injection (Days 3–7)

### Per-Class Protocol
For each fault class (F1–F9), run **20 trials** minimum:

```bash
# Example: 20 trials of WAN degradation (3 min each, with auto cleanup)
for i in $(seq 1 20); do
    sudo python3 pi_scripts/fault_injector.py \
        --fault wan_degraded \
        --duration 180 \
        --split train
    sleep 60  # 60-second cooldown between trials
done
```

### Fault Classes & Commands

| Fault | Command |
|---|---|
| F0 Normal | Baseline collection, no command needed |
| F1 WAN Degraded | `--fault wan_degraded` |
| F2 WAN Down | `--fault wan_down` |
| F3 DNS Fail | `--fault dns_fail` |
| F4 AP Reboot | Smart plug power cycle + `--fault ap_reboot` (manual tag) |
| F5 Coverage Weak | Move probe to dead zone + `--fault coverage_weak` (manual tag) |
| F6 Interference | Start iperf2 flood on Pi, then `--fault interference` |
| F7 AP Overload | Connect 10+ clients, then `--fault ap_overload` |
| F8 LAN Congested | Run `iperf3 -c localhost` locally, then `--fault lan_congested` |
| F9 Probe Fault | Unplug one ESP32, then tag via MQTT `piprobe/control/state` manually |

### Required Data Volume
- ≥ 20 trials × 9 fault classes = **180+ labeled trial windows**
- ≥ 4 time windows per trial = **720+ labeled 60-second windows minimum**

---

## Phase 4: Analysis & Paper Results (Days 8–14)

```bash
# Step 1: Extract features from InfluxDB
python3 analysis/features.py --source influxdb --out data/features.csv

# Step 2: Run calibration analysis
python3 analysis/calibration.py

# Step 3: Train all ML models (full feature set)
python3 analysis/classify_ml.py --features data/features.csv --out data/models

# Step 4: Run ablation study (A1 through A8)
python3 analysis/classify_ml.py --features data/features.csv --out data/models --ablation

# Step 5: Generate all evaluation figures
python3 analysis/evaluate.py --features data/features.csv

# Step 6: Summarize injection log
python3 pi_scripts/label_windows.py
```

Results appear in `data/figures/`:
- `confusion_matrix.png`
- `per_class_metrics.png`
- `ablation_results.png`
- `eval_summary.json`

---

## Reproducibility Checklist

- [ ] All raw telemetry exported to `data/raw/telemetry.csv`
- [ ] Ground-truth labels in `data/labels.csv` and `data/injection_log.csv`
- [ ] Calibration results in `data/calibration/calibration_offsets.csv`
- [ ] Firmware version used in each experiment noted in `experiments/firmware_versions.txt`
- [ ] All figures saved in `data/figures/` at 300 DPI
- [ ] `requirements.txt` pinned and tested on clean install
- [ ] `config/docker-compose.yml` confirmed to reproduce the full stack
