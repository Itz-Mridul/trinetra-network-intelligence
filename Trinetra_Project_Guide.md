# Trinetra: Raspberry Pi 5 + ESP32 Multi-Layer Network Quality Analyzer

**Complete Project Guide – Hardware, Startup, Execution, Low-Cost Strategy & Key Distinctions**

---

## 1. Project Overview

**Title**  
Trinetra: A Low-Cost Raspberry Pi 5 and ESP32 System for Building-Level ISP and Wi-Fi Performance Monitoring, Fault Classification, and Location-Aware Diagnosis (with Cellular Range Mapping)

**Goal**  
Build a practical, low-cost system that measures and distinguishes:
- ISP / WAN issues (Jio, BSNL, Vodafone-Idea, others)
- Local Wi-Fi coverage, interference and dead zones
- LAN / router problems
- Cellular network range and signal quality inside premises

**Core Idea**  
Use a Raspberry Pi 5 (Ethernet-connected) as the wired baseline + central server, and ESP32 boards as distributed Wi-Fi probes. Optionally add a 4G LTE modem to map cellular coverage of Jio, BSNL and Vodafone-Idea.

---

## 2. Hardware Details

### 2.1 Core Hardware (Wi-Fi + ISP Diagnosis)

| Item                              | Qty | Approx. Cost (INR) | Purpose                                      |
|-----------------------------------|-----|--------------------|----------------------------------------------|
| Raspberry Pi 5 (4 GB or 8 GB)     | 1   | 7,000 – 10,000     | Central gateway, wired baseline, dashboard   |
| Official 27 W Power Supply        | 1   | 800 – 1,200        | Stable power                                 |
| Active Cooler / Heatsink          | 1   | 400 – 600          | Thermal management                           |
| 64/128 GB microSD (A2 class)      | 1   | 600 – 1,000        | OS + data storage                            |
| Ethernet Cable + Case             | 1   | 300 – 600          | Wired connection to router/ONT               |
| ESP32 DevKit (WROOM / WROVER)     | 2–4 | 250 – 400 each     | Distributed Wi-Fi probes                     |
| USB cables / 5 V supplies         | 2–4 | 150 – 300 each     | Power for ESP32 probes                       |

**Core Subtotal**: ₹10,000 – 15,000

### 2.2 Cellular Range Extension (Jio / BSNL / Vodafone-Idea)

| Item                                      | Qty | Approx. Cost (INR) | Notes                                                                 |
|-------------------------------------------|-----|--------------------|-----------------------------------------------------------------------|
| Waveshare SIM7600G-H 4G HAT (or A7670)    | 1   | 6,000 – 8,000      | Supports Indian LTE bands (Jio B40/B41, Airtel, Vi, BSNL). Has GNSS |
| External LTE Antennas (main + diversity)  | 1–2 | 300 – 800          | Better indoor reception                                               |
| Nano-SIM cards (prepaid data)             | 1–3 | 15 – 200 each      | One each for Jio, BSNL, Vi – swap for multi-operator tests            |
| Optional second modem / USB 4G dongle     | 1   | 2,000 – 5,000      | Simultaneous multi-operator readings                                  |
| Power bank + portable enclosure           | 1   | 1,000 – 2,000      | For walk-around surveys                                               |

**Full System with Cellular**: ₹18,000 – 25,000

### 2.3 Optional / Future Add-ons
- GPS module (already present on most SIM7600 HATs)
- Extra ESP32 probes for more rooms/floors
- USB Wi-Fi adapter on Pi (secondary radio)
- OLED displays on probes for local feedback

---

## 3. Software Stack

| Layer              | Tools / Libraries                          | Purpose                                      |
|--------------------|--------------------------------------------|----------------------------------------------|
| Operating System   | Raspberry Pi OS 64-bit                     | Base system                                  |
| Containerization   | Docker + Docker Compose                    | Easy deployment of services                  |
| Messaging          | Mosquitto (MQTT)                           | ESP32 → Pi telemetry                         |
| Database           | InfluxDB or TimescaleDB / PostgreSQL       | Time-series storage                          |
| Visualization      | Grafana + FastAPI (optional)               | Live dashboard + heatmaps + reports          |
| Network Tools      | iperf3, speedtest-cli, mtr, ping, dig      | Throughput, speed, latency, traceroute       |
| Cellular           | ModemManager (`mmcli`), AT commands        | RSRP, RSRQ, SINR, operator info              |
| ESP32 Firmware     | Arduino IDE or ESP-IDF                     | Scan, connect, measure, publish              |
| Analysis           | Python 3                                   | Classification rules, heatmap generation     |

---

## 4. How to Start and Execute the Complete Project

### Phase 0 – Preparation (1–2 days)
1. Procure core hardware (Pi 5 + 1–2 ESP32).
2. Obtain simple floor plans of the premises.
3. Buy prepaid SIMs for Jio and BSNL/Vi (if cellular is required).
4. Ensure authorized access to the networks under test.

### Phase 1 – Raspberry Pi Baseline (Week 1)
1. Flash Raspberry Pi OS and enable SSH.
2. Connect Pi to router/ONT via **Ethernet** (critical for clean WAN baseline).
3. Install essentials:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose python3-pip iperf3 mtr speedtest-cli
   ```
4. Create a simple continuous test loop:
   - Ping gateway + external targets (8.8.8.8, 1.1.1.1)
   - DNS lookup timing
   - Periodic speed tests
   - Store results in CSV or InfluxDB
5. This already answers: “Is the ISP/WAN healthy?”

### Phase 2 – First ESP32 Wi-Fi Probe (Week 1–2)
1. Flash ESP32 with firmware that:
   - Scans nearby APs (SSID, BSSID, RSSI, channel)
   - Connects to authorized Wi-Fi
   - Measures ping/RTT and packet loss to Pi and gateway
   - Publishes JSON via MQTT or HTTP every 30–60 seconds
2. On Pi: receive data and display (even simple Python print is enough initially).
3. Place probe in one room and verify readings change with movement.

### Phase 3 – Cellular Capability (Week 2–3)
1. Attach SIM7600 HAT (or USB modem) to Pi.
2. Insert SIM and test:
   ```bash
   sudo apt install modemmanager
   mmcli -L
   mmcli -m 0
   mmcli -m 0 --signal-get
   ```
3. Useful AT commands:
   - `AT+CSQ` → basic signal quality
   - `AT+CPSI?` / `AT+CESQ` → RSRP, RSRQ, SINR, band
   - `AT+COPS?` → current operator
4. Log: timestamp, operator, RSRP, RSRQ, SINR, room ID (or GPS).
5. Multi-operator method:
   - Swap SIMs and re-measure same points (lowest cost)
   - Or use two modems for simultaneous comparison

### Phase 4 – Unified System & First Survey (Week 3–4)
1. Combine Wi-Fi probe data + Pi wired metrics + cellular readings into one database.
2. Perform walk-around survey:
   - At each marked point record Wi-Fi RSSI + cellular RSRP
   - Tag with room ID or coordinates
3. Generate basic heatmaps (matplotlib / plotly over floor-plan image).
4. Implement simple rule-based fault classification.

### Phase 5 – Multi-Probe + Dashboard + Reporting (Week 5–8)
1. Deploy 3–6 fixed ESP32 probes at key locations (near AP, far corner, corridor, high-density room, different floors).
2. Build Grafana dashboard with:
   - Live metrics
   - Location-based maps
   - Signal-strength heatmaps (Wi-Fi + Cellular)
   - Historical trends
   - Downloadable incident reports
3. Refine classification engine and automated alerts.

### Phase 6 – Validation & Documentation
- Controlled experiments (peak vs off-peak, different operators, with/without extra APs)
- Document results, limitations and ethics
- Prepare for demo / paper / report

---

## 5. Low-Cost Strategy

| Strategy                              | How to Apply                                                                 | Savings / Benefit                  |
|---------------------------------------|------------------------------------------------------------------------------|------------------------------------|
| Start minimal                         | Pi 5 + 1 ESP32 first; add cellular and extra probes later                    | Lowest entry cost                  |
| Reuse open-source stacks              | Adapt internet-pi, isp-monitor, python-wifi-survey-heatmap patterns          | Avoid rewriting everything         |
| SIM swapping                          | One modem + multiple prepaid SIMs instead of multiple modems                 | Saves ₹4,000–10,000                |
| Manual location tags                  | Use room IDs on floor plan instead of full GPS for indoor surveys            | No extra GPS hardware needed       |
| Docker on Pi                          | Easy to deploy and update services without complex native installs           | Time & reliability                 |
| Approximate throughput on ESP32       | Use HTTP download tests instead of full iperf3 client if memory limited      | Simpler firmware                   |
| Shared power supplies                 | Use wall adapters for fixed probes; power bank only for mobile survey unit   | Lower recurring cost               |
| Open-source visualization             | Grafana + free plugins instead of commercial dashboard tools                 | Zero license cost                  |

**Target total cost for demonstrable system**: ₹12,000 – 20,000 (core + basic cellular).

---

## 6. Important Distinctions & Key Points

### 6.1 What Each Device Measures Independently

| Measurement                     | Device          | Notes                                      |
|---------------------------------|-----------------|--------------------------------------------|
| Wi-Fi RSSI, channel, BSSID      | ESP32           | Coverage and interference                  |
| Local RTT, jitter, packet loss  | ESP32 ↔ Pi      | Wi-Fi / LAN quality                        |
| Local throughput                | ESP32 → Pi      | Actual usable speed on Wi-Fi               |
| WAN latency, DNS, speed, loss   | Pi (Ethernet)   | Clean ISP/WAN baseline                     |
| Cellular RSRP / RSRQ / SINR     | 4G LTE modem    | Cellular coverage of specific operator     |
| Operator name & band            | 4G LTE modem    | Confirms Jio / BSNL / Vi                   |

### 6.2 Critical Distinctions (Never Confuse These)

- **Weak Wi-Fi signal ≠ Slow Internet**  
  Always compare against Pi Ethernet baseline.

- **Good RSSI can still mean poor performance**  
  High interference, co-channel congestion or AP overload can degrade experience.

- **Cellular RSRP is not the same as Wi-Fi RSSI**  
  Different technologies, different units and thresholds.

- **ISP identity must be confirmed**  
  Do not rely only on SSID (user-configurable). Technician should label the ISP.

- **One-time reading is insufficient**  
  Capture time-series variation (peak vs off-peak, minutes/hours/days).

- **ESP32 is not professional survey equipment**  
  Excellent for relative comparison and low-cost mapping; absolute accuracy is limited.

- **Authorization & Privacy**  
  Use only authorized networks. Do not capture payloads or track devices without consent.

### 6.3 Fault Classification Logic (Examples)

| Observed Pattern                                      | Probable Cause                  | Evidence Strength |
|-------------------------------------------------------|---------------------------------|-------------------|
| Pi wired poor; all probes show high external latency  | ISP / WAN degradation           | Strong            |
| Pi wired good; far room weak RSSI + high local RTT    | Wi-Fi coverage hole             | Strong            |
| Good RSSI but high loss/jitter + many APs on channel  | Co-channel interference         | Medium–Strong     |
| Problem only at peak hours, RSSI stable               | AP / router load or congestion  | Medium            |
| Drops only while moving between rooms                 | Roaming / AP overlap gap        | Medium            |
| Single room intermittent, others stable               | Local obstruction / interference| Medium            |
| Only one remote website slow                          | Remote service / path issue     | Strong            |
| Weak cellular RSRP in specific rooms                  | Cellular coverage gap           | Strong            |

Always report raw measurements together with the classification.

---

## 7. Network Testing Methodology Summary

**Metrics to collect**
- RSSI (dBm), SNR, channel, nearby AP count
- Gateway RTT, packet loss, jitter
- Internet RTT, DNS lookup time, HTTP TTFB
- Local throughput (TCP/UDP) and WAN download/upload
- Cellular RSRP, RSRQ, SINR, band, operator
- Time-series fluctuation (standard deviation of RSSI / RTT)

**Test types**
- Continuous monitoring (fixed probes, 30–60 s interval)
- One-time walk-around survey (location-tagged)
- Incident-triggered deep tests (MTR, full speed test)

**Comparison dimensions**
- Different rooms / floors
- Different operators (Jio vs BSNL vs Vi)
- Peak vs off-peak times
- Before / after AP repositioning or channel change

---

## 8. Keywords

`Raspberry Pi 5`, `ESP32`, `Wi-Fi site survey`, `network diagnostics`, `ISP monitoring`, `Jio`, `BSNL`, `Vodafone-Idea`, `cellular coverage mapping`, `RSRP`, `RSSI`, `latency`, `jitter`, `packet loss`, `throughput`, `iperf3`, `MQTT`, `InfluxDB`, `Grafana`, `heatmap`, `floor-plan mapping`, `fault classification`, `WAN baseline`, `low-cost IoT`, `building network testing`, `SIM7600`, `ModemManager`, `AT commands`, `multi-layer diagnosis`, `coverage hole`, `co-channel interference`, `roaming`, `time-series monitoring`

---

## 9. Quick Start Checklist

- [ ] Buy Raspberry Pi 5 + power + microSD
- [ ] Buy 1–2 ESP32 boards
- [ ] (Optional) Buy SIM7600 4G HAT + SIMs
- [ ] Flash Pi OS and connect via Ethernet
- [ ] Run basic ping + speedtest loop
- [ ] Flash first ESP32 with scan + MQTT code
- [ ] Verify end-to-end telemetry
- [ ] Add cellular modem and test `mmcli --signal-get`
- [ ] Perform first room-by-room survey
- [ ] Generate simple heatmap
- [ ] Expand to multi-probe + full dashboard

---

## 10. Research & Ethics Notes

- ESP32 and low-cost LTE modems are excellent for relative measurements and educational/research prototypes.
- They are **not** substitutes for calibrated professional RF survey equipment.
- Always obtain authorization before testing any network.
- Do not capture Wi-Fi payloads or personal device identifiers without clear lawful purpose and consent.
- Avoid any deauthentication, disruption or offensive wireless techniques.

---

**Document Version**: 1.0  
**Based on**: Project discussion and prior-work analysis (ESP32 + Raspberry Pi 5 Network Testing Tool)  
**Focus**: Practical, modular, low-cost implementation suitable for engineering project, research paper or demonstration.
