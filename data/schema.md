# Trinetra Telemetry & Ground-Truth Schema
Version: 1.0 (Research Edition)  
Standard: Aligned with IEEE I²MTC 2027 Experimental Protocol

---

## 1. MQTT Topics & Message Formats

### 1.1 Topic: `piprobe/pi/wan` (Wired Baseline)
Published by: Raspberry Pi 5 (`eth0` interface)  
Cadence: Every 10–30 seconds (configurable)  
Payload Format: JSON

```json
{
  "timestamp": 1729725300.123,
  "probe_id": "pi5_gateway",
  "layer": "wan",
  "room_id": "server_corner",
  "gw_rtt_mean_ms": 1.42,
  "gw_rtt_std_ms": 0.21,
  "gw_loss_pct": 0.0,
  "inet_rtt_mean_ms": 14.85,
  "inet_rtt_std_ms": 1.15,
  "inet_loss_pct": 0.0,
  "dns_latency_ms": 18.4,
  "http_ttfb_ms": 64.2,
  "wan_tput_dl_mbps": 94.5,
  "wan_tput_ul_mbps": 48.2,
  "cpu_temp_c": 44.5,
  "mem_used_pct": 28.1,
  "fault_class": "normal",
  "run_id": "baseline_run_001"
}
```

### 1.2 Topic: `piprobe/+/wifi` (ESP32 Probes)
Published by: ESP32 Probes (`esp_probe_1`, `esp_probe_2`, etc.)  
Cadence: Every 10–15 seconds  
Payload Format: JSON

```json
{
  "timestamp": 1729725300.540,
  "probe_id": "esp_probe_1",
  "mac": "24:6F:28:XX:XX:XX",
  "layer": "wifi",
  "room_id": "R1_living_room",
  "rssi_raw_dbm": -62,
  "rssi_calibrated_dbm": -60.8,
  "channel": 6,
  "bssid": "AA:BB:CC:DD:EE:FF",
  "ap_count_total": 8,
  "ap_count_on_channel": 4,
  "gw_rtt_mean_ms": 5.8,
  "gw_rtt_jitter_ms": 1.4,
  "gw_loss_pct": 0.0,
  "pi_rtt_mean_ms": 5.2,
  "pi_rtt_jitter_ms": 1.2,
  "pi_loss_pct": 0.0,
  "tput_kbps": 18500,
  "reconnect_count": 0,
  "uptime_sec": 3600,
  "free_heap_bytes": 142380,
  "fault_class": "normal",
  "run_id": "baseline_run_001"
}
```

---

## 2. InfluxDB 2.x Measurement Schema

### 2.1 Measurement: `network_telemetry`

#### Tags (Indexed for fast slicing & train/test splitting):
- `layer`: `["wan", "wifi"]`
- `probe_id`: `["pi5_gateway", "esp_probe_1", "esp_probe_2", "esp_probe_3", ...]`
- `room_id`: `["R1_living_room", "R2_bedroom", "R3_corridor", ...]`
- `bssid`: Wi-Fi Access Point MAC address
- `channel`: Primary RF channel (`"1"`, `"6"`, `"11"`, etc.)
- `fault_class`: Ground truth label (see Section 3)
- `run_id`: Unique identifier for each 10-minute trial (e.g., `run_20261023_F1_01`)
- `split`: Generalization tag `["train", "test_time", "test_room", "test_board"]`

#### Fields (Numeric metrics for classification):

`telemetry_received` is a phone heartbeat field. It allows the dashboard to show that the phone agent is connected even when Android temporarily returns no cell-radio values.
- **Wired Baseline (Pi):**
  - `gw_rtt_mean_ms`, `gw_rtt_std_ms`, `gw_loss_pct`
  - `inet_rtt_mean_ms`, `inet_rtt_std_ms`, `inet_loss_pct`
  - `dns_latency_ms`, `http_ttfb_ms`
  - `wan_http_success_pct`, `wan_http_success_count`, `wan_http_target_count`
  - `wan_tput_dl_mbps`, `wan_tput_ul_mbps`
  - `wan_tput_dl_bytes`
  - `pi_cpu_temp_c`, `pi_mem_used_pct`
- **Wireless Telemetry (ESP32):**
  - `rssi_raw_dbm`, `rssi_calibrated_dbm`
  - `ap_count_total`, `ap_count_on_channel`
  - `gw_rtt_mean_ms`, `gw_rtt_jitter_ms`, `gw_loss_pct`
  - `pi_rtt_mean_ms`, `pi_rtt_jitter_ms`, `pi_loss_pct`
  - `tput_kbps`
  - `uptime_sec`, `free_heap_bytes`, `reconnect_count`
- **Cross-Layer Derived (Computed per time window):**
  - `rtt_hop_delta_ms` = `esp_gw_rtt - pi_gw_rtt` (Isolates pure wireless hop latency)
  - `loss_hop_delta_pct` = `esp_gw_loss - pi_gw_loss`

---

## 3. Ground-Truth Fault Class Taxonomy

| Label ID | `fault_class` | Physical Injection Mechanism | Expected Primary Signature |
|---|---|---|---|
| **F0** | `normal` | Baseline, no injection | Stable RSSI, zero packet loss, low RTT across both layers |
| **F1** | `wan_degraded` | `tc netem delay 200ms 50ms loss 5%` on Pi `eth0` | High `inet_rtt` on Pi and ESP32; low `gw_rtt` and strong RSSI |
| **F2** | `wan_down` | Physically unplug WAN router uplink or block gateway default route | Pi and ESP32 gateway ping works; `inet_loss_pct` = 100% |
| **F3** | `dns_fail` | `iptables -A OUTPUT -p udp --dport 53 -j DROP` on Pi/DNS | Ping works fine; `dns_latency_ms` = timeout / -1 |
| **F4** | `ap_reboot` | Power cycle AP via smart plug | ESP32 disassociates (`reconnect_count` increments); Pi Ethernet fine |
| **F5** | `coverage_weak`| Physical probe relocation to dead zone / shielded box | ESP32 `rssi_calibrated` < -75 dBm, increased `gw_rtt`, Pi fine |
| **F6** | `interference` | Competing traffic generator on same channel (`iperf2`) | Strong RSSI (> -65 dBm), elevated `gw_loss` & `jitter`, Pi fine |
| **F7** | `ap_overload`  | 10+ devices running simultaneous video/HTTP load | Stable RSSI, high local `gw_rtt` on all probes, Pi Ethernet fine |
| **F8** | `lan_congested`| Saturate local LAN switch ports | Pi and ESP32 both show high `gw_rtt`, but `rssi` is strong |
| **F9** | `probe_fault`  | Deliberate probe power-cut / watchdog trigger | Probe heartbeat stops; Pi and remaining probes report normal |

---

## 4. Window Aggregation Rules (Feature Extraction for ML)

- **Window Duration:** 60 seconds (non-overlapping).
- **Minimum Valid Samples:** ≥ 4 ESP32 samples and ≥ 2 Pi samples per 60s window.
- **Warmup/Cooldown Exclusion:** Exclude the first 10 seconds and last 10 seconds of every fault transition window to avoid boundary label noise.
