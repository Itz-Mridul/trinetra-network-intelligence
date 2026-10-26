# ESP32 + Raspberry Pi 5 Building Network Testing Tool

## Project context

The proposed project is a low-cost, building-level network diagnostic and monitoring system based on a **Raspberry Pi 5** and one or more **ESP32** probes. It is intended for authorized testing of networks such as Jio and BSNL connections, as well as the Wi-Fi environment inside a building.

The system should distinguish among:

- **ISP/WAN issues:** Internet outage, high external latency, packet loss, DNS failure, poor upload/download performance, routing issues.
- **Local Wi-Fi issues:** Weak RSSI, coverage holes, interference, channel congestion, unstable roaming, or poor access-point placement.
- **LAN/router/device issues:** Router overload, unstable gateway, local packet loss, or a problem isolated to a particular client.

> Note: “JOI” is assumed to mean **Jio**. ISP identity should be technician-confirmed rather than inferred only from a Wi-Fi SSID, because SSIDs are user-configurable.

---

## Initial useful GitHub repositories

### ISP and WAN quality monitoring on Raspberry Pi

| Repository | Link | Description | Relevance |
|---|---|---|---|
| ISP Checker | https://github.com/fmdlc/ISP-Checker | Docker/Kubernetes ISP quality checking using Telegraf, InfluxDB, ping, DNS, HTTP response-time, speed tests, and MTR/traceroute visualization. | Extend it with ISP labels, outage detection, and Jio/BSNL-specific reports. |
| Gonzales | https://github.com/akustikrausch/gonzales | 24/7 Internet speed monitor with automated Ookla Speedtest CLI runs, dashboarding, and outage detection. | Useful for SLA-style long-term ISP reports. |
| TowerWatch | https://github.com/kemosabe102/towerwatch | Tracks latency, jitter, packet loss, DNS/TCP/HTTP timings and sends metrics to Grafana Cloud. | Useful reference for continuous network health measurements. |
| SpeedWatch | https://github.com/aragno-tech/speedwatch | Logs Internet-speed results using SQLite or InfluxDB and Grafana. | Good for long-term speed history. |
| Pinet | https://github.com/mike-weiner/pinet | Raspberry Pi network health monitoring with Prometheus, Telegraf and Grafana. | Reference for a monitoring architecture. |
| Internet Pi | https://github.com/geerlingguy/internet-pi | Raspberry Pi Internet monitoring stack using Prometheus, Grafana, HTTP tests and speed tests. | Strong Pi backend/deployment reference. |
| ISP Monitor | https://github.com/germancorbetta/isp-monitor | Pi ISP monitor built using balena, Telegraf, Speedtest CLI, InfluxDB and Grafana. | Use for a containerized ISP-quality module. |
| ISP Monitor guide | https://github.com/sbehrends/isp-monitor | Telegraf and InfluxDB guide for monitoring ISP quality, including recurring pings and DNS measurements. | Useful for scheduled loss/latency/DNS probes. |
| Grafana Speedtest Dashboard | https://github.com/wildchld-ops/grafana_speedtest_dashboard | Raspberry Pi speed monitor with Speedtest CLI and Grafana visualization. | A simple starting point for speed and ping dashboards. |

### ESP32 Wi-Fi scanning and diagnostics

| Repository | Link | Description | Relevance |
|---|---|---|---|
| ESP32 Wi-Fi Scanner | https://github.com/CyberTechNex/ESP32-WIFI-Scanner | ESP32 scanner with OLED display showing SSID, RSSI and security information. | Start point for room-level Wi-Fi probe firmware. |
| ESP32 Wi-Fi Scanner | https://github.com/dizzpy/ESP32-WiFi-Scanner | Basic ESP32 project for detecting SSID, RSSI and security type. | Minimal codebase to add MQTT/HTTP telemetry. |
| ESP32 Marauder | https://github.com/justcallmekoko/ESP32Marauder | ESP32 Wi-Fi/Bluetooth toolkit with scanning and authorized local network utilities. | Use only authorized diagnostic features; exclude disruptive/security-attack functionality. |
| ESP32 sniffer | https://github.com/ETS-PoliTO/esp32-sniffer | Firmware that observes Wi-Fi probe-request traffic and sends periodic information to a server. | Architectural reference for ESP32-to-server reporting; avoid collection of personal identifiers or payloads. |
| ESP32 Wi-Fi sniffer | https://github.com/patrickhaahr/esp32-wifi-sniffer | Privacy-focused RSSI-based multi-sensor device-detection/trilateration visualizer. | Useful reference for multi-ESP32 dashboards; do not use it to track people/devices without consent. |
| Espressif ESP-CSI | https://github.com/espressif/esp-csi | Espressif examples for Wi-Fi Channel State Information applications. | Advanced/research-oriented option for detailed RF/channel analysis. |
| ESP-Hosted NG | https://github.com/espressif/esp-hosted | Makes an ESP device a Wi-Fi/Bluetooth peripheral for Linux/MCU hosts over SDIO/SPI/UART. | Option for a managed secondary Pi radio, though a standard Wi-Fi adapter may be simpler initially. |

### Wi-Fi building surveys, floor plans and heatmaps

| Repository | Link | Description | Relevance |
|---|---|---|---|
| Python Wi-Fi Survey Heatmap | https://github.com/jantman/python-wifi-survey-heatmap | Linux Wi-Fi site survey application that records measurements around a floor plan and produces signal-strength/throughput heatmaps. Uses `iperf3` for active tests. | Closest prior work for building-wide Wi-Fi range and quality mapping. |
| Wi-Fi Heatmapper | https://github.com/hnykda/wifi-heatmapper | Measures Wi-Fi signal strength and optionally throughput at locations on a floor plan. | Good visual model for room-wise coverage and quality maps. |
| PiNetworkMonitor | https://github.com/YHLeong/PiNetworkMonitor | Raspberry Pi monitoring dashboard for device discovery, latency, packet loss, system health and network status; uses Python, FastAPI, Nmap and SQLite. | Useful reference for a Pi-based local dashboard. |

### General network measurement tools

| Repository | Link | Description | Relevance |
|---|---|---|---|
| iperf / iperf3 | https://github.com/esnet/iperf | Standard active TCP/UDP network performance measurement tool. | Run the server on Pi 5 to measure local throughput, UDP jitter and packet loss independently from the ISP. |
| Diagnose Network | https://github.com/Bre98/diagnose-network | Python network diagnostics with ping, traceroute and interface diagnostics. | Can be adapted into a Pi command-line or API diagnostic service. |

---

## Prior work: ISP and Internet monitoring

### 1. Raspberry Pi Internet measurement agents

Previous research and implementations have shown that Raspberry Pi hardware can be used as a low-cost, always-on Internet measurement agent. Such systems measure Internet reachability, round-trip latency, packet loss and path performance.

**Relevance:** This supports using a Pi 5 as a persistent measurement gateway rather than only as a general-purpose computer.

**Gap:** Many such systems focus on the external Internet path and do not combine local building Wi-Fi diagnostics, ESP32 sensor probes, and ISP-specific incident reports.

### 2. CheesePi

CheesePi is a Raspberry Pi-oriented approach for always-on, reliable monitoring of home Internet connections.

**Relevance:** It supports continuous monitoring of residential or small-office broadband.

**Gap:** It does not provide a distributed ESP32 sensor layer, floor-plan coverage mapping, or automatic separation of ISP, router and Wi-Fi bottlenecks.

### 3. ISP monitoring stacks

Open-source Pi stacks based on Telegraf, InfluxDB, Prometheus, Grafana and Speedtest CLI perform recurring tests for ping, packet loss, DNS resolution, HTTP response time, upload/download speed and service availability.

**Relevance:** These are directly useful for the Pi 5 backend.

**Gap:** They usually do not capture indoor Wi-Fi signal quality, channel congestion, local throughput per room, or time-correlated ESP32 observations.

### 4. Measuring Wi-Fi bottlenecks

Research on home Wi-Fi bottlenecks emphasizes simultaneous access-ISP and in-home Wi-Fi measurements. Poor user experience cannot be attributed to the ISP without comparing a wired/wide-area baseline against the local wireless network.

**Relevance:** This is a core idea for the project.

**Project extension:** Connect the Pi 5 to the router/ONT by Ethernet as a baseline, then compare Pi-to-Internet results with ESP32/client-to-Pi local Wi-Fi tests.

### 5. OpenSignal-style quality metrics

Industry broadband-quality methods use measures such as download speed, upload speed, latency, jitter, packet loss and time-to-first-byte.

**Relevance:** These metrics can define the project evaluation framework.

---

## Prior work: building range and network fluctuation

This category is commonly called **Wi-Fi site surveying**, **wireless coverage mapping**, **indoor RF heatmapping**, and **continuous Wi-Fi performance monitoring**.

### 1. Wi-Fi site surveys

Enterprise Wi-Fi engineers conduct surveys before and after access-point installation. A survey uses building/floor diagrams, records signal characteristics at many locations, identifies obstacles and high-density areas, validates access-point placement, and documents coverage boundaries.

**Main goal:** Identify coverage holes, weak-signal areas, interference, channel congestion, poor roaming zones, and performance changes across rooms/floors/time.

### 2. Wi-Fi heatmap tools

Projects such as `python-wifi-survey-heatmap` and `wifi-heatmapper` collect readings at marked locations and plot heatmaps over a floor plan.

**Typical maps:**

- RSSI/signal-strength heatmap
- Local throughput heatmap
- Packet-loss heatmap
- Gateway latency heatmap
- Jitter heatmap
- Coverage-hole map
- Time-based fluctuation map

### 3. ESP32 radio-map studies

Prior research has used multiple ESP32 devices placed around an office in monitoring mode to collect Wi-Fi signal data and construct indoor radio maps.

**Relevance:** It validates ESP32 as a low-cost indoor Wi-Fi sensing device.

**Project extension:** Add active tests—ping, packet loss, jitter and local throughput—rather than relying only on signal strength.

### 4. ESP32-to-Raspberry Pi data collection

Prior ESP32 systems have collected RSSI data and sent it to a Raspberry Pi acting as a server.

**Relevance:** This closely aligns with the proposed architecture: distributed ESP32 probes collect local readings, while the Pi stores, analyzes and displays results.

### 5. Long-term reliability monitoring

Long-term wireless reliability evaluations use RSSI, round-trip time and packet loss over long periods. This supports observing performance variation rather than taking a single one-time reading.

**Relevance:** A room may look acceptable on average but still fail during peak load or intermittent interference.

---

## What to measure inside a building

| Metric | Meaning | Why it matters |
|---|---|---|
| RSSI in dBm | Received Wi-Fi signal strength | Detects range limits and coverage holes |
| SNR in dB | Difference between desired signal and noise | Strong RSSI can still have poor performance when noise/interference is high |
| SSID/BSSID | Network/access-point identifier | Indicates which AP a probe is seeing or connected to |
| Channel / channel width | Wi-Fi frequency-channel details | Identifies overlap and channel-plan problems |
| Nearby AP count | Number of APs visible on a channel/band | Simple indicator of possible congestion |
| Gateway RTT | Ping time from client/probe to local Pi/router | Separates local wireless delay from Internet delay |
| Internet RTT | Ping time to external target | Detects WAN/ISP delay |
| Jitter | Variation in delay | Important for real-time voice/video and industrial traffic |
| Packet loss | Fraction of packets that fail to arrive | Detects unstable links, interference or overload |
| TCP/UDP throughput | Usable local transfer rate | Represents actual user experience |
| Retry/retransmission rate | Re-sent Wi-Fi frames | Useful interference/weak-signal indicator when available |
| Roaming time | Time lost when moving between APs | Important for corridors, warehouses and multi-AP buildings |
| Time-series variation | Variation over minutes/hours/days | Detects intermittent failures caused by load or interference |

Useful calculations:

\[
\text{Packet loss rate} = rac{\text{lost packets}}{\text{packets sent}} \times 100
\]

\[
\text{RSSI fluctuation} = \sigma(\text{RSSI readings in a time window})
\]

\[
\text{Latency fluctuation} = \sigma(\text{RTT readings in a time window})
\]

---

## Proposed system architecture

### Raspberry Pi 5: central gateway/backend

Connect the Pi 5 to the router or ONT using **Gigabit Ethernet** whenever possible. It provides a wired baseline that is not affected by client Wi-Fi signal conditions.

The Pi 5 should run:

- `iperf3` server for local TCP/UDP throughput, jitter and packet-loss testing
- Ping tests to local gateway and external targets
- DNS lookup tests
- HTTP/HTTPS and time-to-first-byte tests
- Scheduled Internet speed tests
- Traceroute/MTR during detected issues
- MQTT broker or REST API for ESP32 probes
- SQLite/PostgreSQL/InfluxDB for storage
- Grafana or FastAPI dashboard
- Automated report generation for authorized ISP escalation

### ESP32: distributed building probes

Each ESP32 probe can:

- Scan available access points
- Record SSID, BSSID, RSSI, channel and security mode
- Connect to the authorized Wi-Fi network
- Measure ping/RTT to the Pi and router
- Measure packet loss and jitter
- Run controlled local HTTP/TCP tests to the Pi
- Upload telemetry via MQTT or HTTP
- Report its health: uptime, Wi-Fi connection state and temperature/battery if needed

### Suggested data record

```text
timestamp
building_id
floor_id
room_id
probe_id
isp_name
ssid
bssid
band
channel
channel_width
rssi_dbm
snr_db
nearby_ap_count
gateway_ping_ms
gateway_packet_loss_percent
local_jitter_ms
internet_ping_ms
dns_lookup_ms
http_response_ms
local_throughput_mbps
wan_download_mbps
wan_upload_mbps
```

---

## Building survey methodology

### One-time mapping survey

1. Obtain a scaled floor plan for every floor.
2. Mark rooms, corridors, stairs, halls, high-user-density zones and known complaint locations.
3. Make a survey grid:
   - At least one reading in each small room.
   - Multiple readings in large rooms, halls and corridors.
   - Readings near exterior walls, staircases and apparent coverage edges.
4. At each location, record:
   - SSID and BSSID
   - Wi-Fi band, channel and channel width
   - RSSI and SNR where available
   - Nearby AP count/channel observations
   - Ping to Pi 5 and router
   - Packet loss and jitter
   - Local `iperf3`/HTTP throughput to Pi 5
   - External Internet latency, DNS and HTTP timing
5. Upload measurements with location label and timestamp.
6. Generate heatmaps for RSSI, throughput, latency, jitter, packet loss and fluctuation score.

### Continuous monitoring survey

Install fixed probes at representative locations:

- Near the router or AP
- Farthest room/corner from an AP
- Corridor or roaming boundary
- High-client-density room
- Each floor
- Known poor-coverage location

Each ESP32 can submit data every 30–60 seconds. Keep raw data for analysis and generate hourly/daily summaries.

---

## Fault classification examples

| Observed result | Likely diagnosis | Recommended action |
|---|---|---|
| Pi wired speed is poor; all probes show high external latency/loss | ISP/WAN degradation | Preserve speed, ping, DNS, traceroute and outage evidence; escalate to ISP |
| Pi wired Internet is good; far room has weak RSSI, high local RTT and poor local throughput | Wi-Fi coverage hole | Reposition/add wired AP or mesh node; inspect placement |
| RSSI is reasonably strong but jitter/loss are high; nearby AP count on same channel is high | Co-channel contention/interference | Improve channel plan; favor 5 GHz/6 GHz when supported; review channel width |
| Problem occurs only at peak times while RSSI stays stable | AP/router load, uplink bottleneck or congestion | Check client count, AP CPU, router performance, backhaul and QoS |
| Connection drops while walking through a corridor/staircase | Roaming problem or AP-overlap gap | Adjust AP position/power/channel plan; verify roaming configuration |
| A single room has periodic drops while the rest are stable | Local obstruction/interference | Check walls, metal storage, elevators, microwave devices, Bluetooth/IoT density and AP placement |
| Pi-to-Internet is healthy but only one website is slow | Remote service/path issue | Test multiple targets; record DNS and traceroute evidence |

---

## Project research gap

Existing projects usually solve only one part of the problem:

- Site-survey tools make RSSI/throughput heatmaps.
- Pi monitoring tools measure Internet uptime, latency, packet loss, DNS and speed.
- ESP32 projects scan Wi-Fi and report RSSI.

The proposed system combines these layers in one low-cost building-level platform:

- ESP32 probes for distributed Wi-Fi sensing
- Raspberry Pi 5 for a wired baseline and test orchestration
- Local active performance tests
- WAN/ISP quality monitoring
- Floor-plan heatmaps
- Long-term fluctuation analysis
- Automated root-cause classification
- Unified dashboard and downloadable incident evidence

---

## Suggested project title

**Trinetra: A Raspberry Pi 5 and ESP32-Based Multi-Layer Network Quality Analyzer for ISP and Wi-Fi Fault Diagnosis**

Alternative title:

**Low-Cost Building-Wide Wi-Fi Coverage and ISP Performance Monitoring Using ESP32 and Raspberry Pi 5**

---

## Suggested concise previous-work paragraph

Several open-source projects provide parts of a building-level network diagnostic system. `python-wifi-survey-heatmap` and `wifi-heatmapper` perform Wi-Fi site surveys by collecting signal-strength and throughput observations at floor-plan locations and generating visual heatmaps. Raspberry Pi projects such as `PiNetworkMonitor`, `internet-pi`, and `isp-monitor` monitor local-device availability, latency, packet loss, Internet speed, DNS and ISP service quality. ESP32 projects provide low-cost Wi-Fi scanning, RSSI measurement and wireless telemetry. However, these projects normally address only one layer: Wi-Fi coverage, local-network health, or ISP/WAN performance. The proposed Raspberry Pi 5 and ESP32 system integrates distributed probes, local active testing, WAN monitoring, floor-plan mapping, time-series fluctuation analysis and automated fault classification in one building-level platform.

---

## Limitations and safe-use notes

- ESP32 is well suited to low-cost RSSI scanning, basic active tests and telemetry, but it is not a substitute for calibrated professional Wi-Fi survey equipment.
- RSSI alone is insufficient. Interpret it together with packet loss, jitter, local throughput, channel information and time-based variation.
- For reliable WAN testing, connect Pi 5 to the router/ONT through Ethernet.
- Use only authorized networks and systems.
- Do not capture Wi-Fi payloads or collect/retain personal device identifiers without a clear lawful purpose, consent and an appropriate privacy policy.
- Avoid deauthentication, disruption, credential collection, spoofing and other offensive wireless functions.
