# Trinetra Workflow: Raspberry Pi 5 + ESP32 Wi-Fi and ISP Analyzer (No Cellular, No Waveshare)

Scope: building-level Wi-Fi and WAN fault diagnosis. No SIM7600, no modem, no phone cellular logging.

---

## 1. Goal

Measure and tell apart:
- ISP / WAN problems
- Wi-Fi coverage holes and interference
- LAN / router / AP problems

Core idea: Pi 5 on Ethernet = clean wired baseline + central server. ESP32 boards = cheap distributed Wi-Fi probes. Compare wired vs wireless to locate fault layer.

---

## 2. Scope Change vs Original Guide

Removed:
- Waveshare SIM7600G-H HAT, antennas, power bank for survey, extra SIMs
- ModemManager, `mmcli`, AT commands
- Cellular RSRP / RSRQ / SINR mapping, Jio vs BSNL vs Vi cellular comparison
- Cellular rule in classifier
- Phase 3 of original roadmap

Kept: everything else (Pi baseline, ESP32 probes, MQTT, DB, Grafana, heatmaps, classifier, validation).

Report title suggestion:
**Trinetra: A Low-Cost Raspberry Pi 5 and ESP32 System for Building-Level ISP and Wi-Fi Performance Monitoring, Fault Classification, and Location-Aware Diagnosis**

Limit to state honestly: single wired ISP per site. Multi-ISP comparison only if building has two wired uplinks, or by repeating baseline at other sites or times.

---

## 3. Hardware (Basic Components)

- Raspberry Pi 5, 4 GB enough (₹7,000–10,000)
- Official 27 W USB-C supply (₹800–1,200)
- Active cooler (₹400–600)
- 64 GB microSD, A2 class (₹600–1,000)
- Ethernet cable + case (₹300–600)
- ESP32 DevKit WROOM or WROVER, 2–4 pcs (₹250–400 each)
- USB cables + 5 V adapters, 2–4 pcs (₹150–300 each)
- Optional: USB power bank for mobile ESP32 walk-around (₹800–1,500)
- Optional: laptop (own) for walk survey with `python-wifi-survey-heatmap`
- Optional: USB Wi-Fi adapter for Pi (second radio)
- Optional: OLED on probe for local readout

**Total: about ₹11,000–15,000.**

Free extra probe: Pi own `wlan0`. Use only after Ethernet baseline stable.

ESP32 note: classic WROOM is 2.4 GHz only. 5 GHz not seen. State in report. ESP32-C5 supports 5 GHz if needed.

---

## 4. Tech Stack

| Layer | Tool | Job |
|---|---|---|
| OS | Raspberry Pi OS 64-bit Lite | Base |
| Container | Docker + Compose | Deploy services |
| Broker | Mosquitto | ESP32 to Pi telemetry |
| Ingest | Telegraf (`mqtt_consumer`) | MQTT to DB, no custom code |
| Database | InfluxDB 2.x | Time series |
| Dashboard | Grafana | Live graphs, alerts |
| Wired tests | Python 3 + `ping`, `dig`, `mtr`, `speedtest-cli`, `iperf3` | WAN baseline |
| ESP32 firmware | Arduino IDE (simple) or ESP-IDF (better ping, throughput) | Scan, connect, measure, publish |
| Analysis | Python, pandas, matplotlib or plotly | Heatmaps, classifier |
| Walk survey | `python-wifi-survey-heatmap` | Free laptop survey over floor plan |
| Optional API | FastAPI | Reports endpoint |

---

## 5. Architecture

```
ESP32 probes (Wi-Fi) ─┐
Pi wired tests ───────┼─ MQTT ─> Mosquitto ─> Telegraf ─> InfluxDB ─> Grafana
Pi wlan0 (optional) ──┘                                        └─> Python: heatmap + classifier
```

Rule: Pi baseline always over Ethernet. Never Wi-Fi.

---

## 6. Workflow by Phase

### Phase 0: Preparation (1–2 days)
1. Get floor plan of premises.
2. Mark grid points. Label rooms R1, R2, R3... Room ID replaces GPS.
3. Record router/AP positions on plan.
4. Technician confirms ISP name. Do not trust SSID.
5. Get written permission for network under test.
6. Buy Pi kit + ESP32s.

### Phase 1: Pi Baseline (Week 1)
1. Flash OS with Raspberry Pi Imager. Enable SSH. Hostname `piprobe`.
2. Plug Ethernet into router/ONT.
3. Install tools:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 python3-pip iperf3 mtr-tiny dnsutils
   pip3 install speedtest-cli paho-mqtt --break-system-packages
   ```
4. `docker-compose.yml`:
   ```yaml
   services:
     mosquitto:
       image: eclipse-mosquitto:2
       ports: ["1883:1883"]
       volumes: ["./mosquitto.conf:/mosquitto/config/mosquitto.conf"]
     influxdb:
       image: influxdb:2
       ports: ["8086:8086"]
       volumes: ["influx:/var/lib/influxdb2"]
     telegraf:
       image: telegraf
       volumes: ["./telegraf.conf:/etc/telegraf/telegraf.conf:ro"]
       depends_on: [mosquitto, influxdb]
     grafana:
       image: grafana/grafana
       ports: ["3000:3000"]
       volumes: ["grafana:/var/lib/grafana"]
   volumes: {influx: {}, grafana: {}}
   ```
5. Mosquitto: password file on, anonymous off, LAN only.
6. Telegraf: `inputs.mqtt_consumer` on `piprobe/#`, `data_format = "json"`, parse topic into tags (probe, layer). Output `influxdb_v2`.
7. Write `wan_probe.py`, loop every 60 s:
   - ping gateway, 8.8.8.8, 1.1.1.1: RTT avg, jitter (stddev), loss
   - `dig` timing, 2–3 domains
   - HTTP TTFB, 2–3 sites
   - speed test every 30–60 min only
   - publish JSON to `piprobe/pi/wan`
8. Run as systemd service. Reboot test.

Check: Grafana shows WAN graphs. ISP health question answered.

### Phase 2: First ESP32 Probe (Week 1–2)
Firmware loop every 30–60 s:
1. Scan APs: SSID, BSSID, RSSI, channel. Count APs per channel.
2. Connect to authorized Wi-Fi. Log own RSSI, channel, BSSID. BSSID change = roaming event.
3. Ping gateway and Pi, 10 packets: RTT avg, jitter, loss. Arduino: `ESP32Ping`. ESP-IDF: `esp_ping`.
4. Throughput: HTTP GET 1 MB file from nginx on Pi, time it. ESP-IDF iperf example only talks to iperf2 server, not iperf3.
5. NTP sync. Fallback: Pi stamps on arrival.
6. Publish JSON via PubSubClient to `piprobe/esp1/wifi`:
   ```json
   {"probe":"esp1","room":"R3","rssi":-67,"ch":6,"bssid":"aa:bb:cc:dd:ee:ff",
    "ap_count_ch":5,"gw_rtt":4.2,"gw_jit":1.1,"gw_loss":0,
    "pi_rtt":3.9,"tput_kbps":18400}
   ```
7. Add reconnect logic, hardware watchdog. Store `room` in NVS so no reflash to move probe.

Check: carry probe room to room on power bank. RSSI changes. Data lands in InfluxDB.

### Phase 3: Unified Data and First Survey (Week 3)
1. One schema for all points: `timestamp, layer (wan|wifi), source, room, metrics`.
2. Walk survey:
   - Stand 30–60 s at each grid point.
   - Record RSSI, local RTT, jitter, loss, throughput, room ID.
   - Laptop option: `python-wifi-survey-heatmap` with floor plan image. Zero cost.
3. Heatmap script: pandas group by room or coordinate, interpolate, overlay floor plan with matplotlib or plotly. One map per metric.
4. First rule-based classifier (section 8).

### Phase 4: Multi-Probe, Dashboard, Reporting (Week 4–6)
1. Place 3–6 fixed ESP32 probes: next to AP, far corner, corridor, dense room, other floors. Wall adapters for power.
2. Grafana panels:
   - WAN: RTT, loss, DNS, speed test
   - Per probe: RSSI, RTT, jitter, throughput, channel
   - Heatmap images
   - Classifier verdict with raw numbers beside it
   - Historical trends, peak vs off-peak
3. Alerts: Grafana rule, email or Telegram, e.g. WAN loss above 2 percent for 5 min.
4. Incident-triggered deep test: on alert, Pi runs `mtr` + full speed test, saves report file.
5. Downloadable incident report (FastAPI endpoint or script output).

### Phase 5: Validation and Documentation (Week 6–7)
Experiments:
- Peak vs off-peak
- Before/after AP move
- Before/after channel change
- Add/remove extra AP

Fault injection (check classifier catches each):
- Unplug router uplink: expect WAN fault
- Move AP far from probe: expect coverage hole
- Force busy channel: expect interference
- Block probe with metal or thick wall: expect local obstruction

Write: results, limits, ethics, raw data with every claim.

---

## 7. Metrics to Collect

Wired (Pi):
- Gateway RTT, jitter, loss
- Internet RTT, loss (8.8.8.8, 1.1.1.1)
- DNS lookup time
- HTTP TTFB
- Download / upload speed
- `mtr` hop path on incident

Wi-Fi (ESP32):
- RSSI (dBm), channel, BSSID, nearby AP count, per-channel AP count
- Local RTT, jitter, loss to gateway and Pi
- Local throughput
- Time-series spread: stddev of RSSI and RTT
- Roaming events (BSSID change)

Test types:
- Continuous monitoring, 30–60 s interval
- One-time location-tagged walk survey
- Incident-triggered deep test

Compare across: rooms, floors, peak vs off-peak, before vs after changes.

---

## 8. Fault Classification

| Observed pattern | Probable cause | Evidence |
|---|---|---|
| Pi wired poor, all probes show high external latency | ISP / WAN degradation | Strong |
| Pi wired good, far room weak RSSI, high local RTT | Wi-Fi coverage hole | Strong |
| Good RSSI, high loss/jitter, many APs on channel | Co-channel interference | Medium to strong |
| Problem only at peak hours, RSSI stable | AP / router load | Medium |
| Drops only while moving between rooms | Roaming gap | Medium |
| One room intermittent, others stable | Local obstruction / interference | Medium |
| Only one remote site slow | Remote service / path issue | Strong |

Starter code:
```python
def classify(wan, wifi):
    if wan["loss"] > 2 or wan["rtt"] > 3 * wan["rtt_base"]:
        if all(p["ext_rtt_high"] for p in wifi["all_probes"]):
            return "ISP/WAN degradation", "strong"
    if wan["ok"] and wifi["rssi"] < -75 and wifi["gw_rtt"] > 20:
        return "Wi-Fi coverage hole", "strong"
    if wifi["rssi"] > -65 and (wifi["gw_loss"] > 2 or wifi["gw_jit"] > 15) \
            and wifi["ap_count_ch"] >= 4:
        return "Co-channel interference", "medium"
    if wifi["rssi_std"] < 3 and wifi["peak_hours"] \
            and wifi["gw_rtt"] > 2 * wifi["gw_rtt_base"]:
        return "AP/router congestion", "medium"
    return "No fault / inconclusive", "n/a"
```
Tune thresholds from own baseline data. Always show raw measurements with verdict.

---

## 9. Key Distinctions

- Weak Wi-Fi signal does not equal slow internet. Compare with Pi Ethernet baseline.
- Good RSSI can still mean poor performance (interference, AP overload).
- ISP identity: technician labels it. SSID is user-editable.
- One reading is not enough. Capture time series.
- ESP32 is not professional survey gear. Good for relative comparison, not absolute accuracy.
- ESP32 antenna weak and orientation sensitive. Fix mounting, note orientation.
- Pi on Wi-Fi ruins baseline. Ethernet always.
- Speed test sparingly. Data and ISP fair-use burn fast.

---

## 10. Low-Cost Rules

- Start Pi + 1 ESP32. Add probes after pipeline proven.
- Room IDs instead of GPS.
- HTTP download test instead of iperf on ESP32.
- Telegraf instead of custom ingest code.
- Laptop for walk survey instead of new hardware.
- Open-source stack only: zero license cost.
- Reuse patterns from `internet-pi`, `isp-monitor`, `python-wifi-survey-heatmap`.

---

## 11. Timeline

- Week 1: prep + Pi baseline
- Week 1–2: first ESP32 probe
- Week 3: unified data + first survey + heatmap
- Week 4–6: multi-probe + dashboard + alerts
- Week 6–7: validation + report

---

## 12. Quick Start Checklist

- [ ] Floor plan + room IDs + written permission
- [ ] Buy Pi 5 kit + 2 ESP32
- [ ] Flash Pi OS, connect Ethernet
- [ ] Docker stack up (Mosquitto, Telegraf, InfluxDB, Grafana)
- [ ] `wan_probe.py` running as systemd service
- [ ] ESP32 firmware: scan, connect, ping, publish MQTT
- [ ] Data visible in Grafana
- [ ] First walk survey + heatmap
- [ ] Classifier tested with injected faults
- [ ] 3–6 fixed probes + dashboard + alerts
- [ ] Validation experiments + report

---

## 13. Ethics and Limits

- Use only authorized networks.
- No Wi-Fi payload capture. No device tracking without consent.
- No deauthentication, jamming, or disruptive wireless techniques.
- ESP32 results relative, not calibrated RF measurements.
- Cellular coverage not measured in this version.
- 2.4 GHz only with classic ESP32.

---

## 14. Keywords

`Raspberry Pi 5`, `ESP32`, `Wi-Fi site survey`, `network diagnostics`, `ISP monitoring`, `RSSI`, `latency`, `jitter`, `packet loss`, `throughput`, `iperf3`, `MQTT`, `Telegraf`, `InfluxDB`, `Grafana`, `heatmap`, `floor-plan mapping`, `fault classification`, `WAN baseline`, `low-cost IoT`, `building network testing`, `coverage hole`, `co-channel interference`, `roaming`, `time-series monitoring`
