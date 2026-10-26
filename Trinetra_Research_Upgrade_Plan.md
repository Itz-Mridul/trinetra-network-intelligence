# Trinetra Research Upgrade Plan
## Synthesizing Peer-Review Feedback → Publication-Ready Methodology

**Target**: IEEE I²MTC 2027 (Full paper deadline: December 4, 2026)  
**Proposed title**: *Trinetra: Calibrated Cross-Layer Diagnosis of Indoor Wi-Fi and WAN Faults Using Low-Cost Distributed Probes*  
**Current date**: October 13, 2026 → ~7 weeks to deadline

> [!IMPORTANT]
> This document maps the peer-review critique directly to gaps in `Trinetra_Workflow_No_Cellular.md` and `Trinetra_Project_Guide.md`. Read those first. Cellular is **deferred** to future work per the feedback.

---

## Gap Analysis: Existing Docs vs. Research Requirements

| Requirement | Existing Coverage | Gap Level |
|---|---|---|
| Measurement calibration / uncertainty | Mentioned as caveat only | 🔴 Critical |
| Controlled fault-injection testbed | Phase 5 brief mention | 🔴 Critical |
| Wired Pi baseline as ground-truth | Described well | 🟡 Needs formalization |
| Cross-layer synchronized collection | Architecture exists | 🟡 Needs sync protocol |
| Explainable ML classification | Rule-based starter only | 🔴 Critical |
| Generalization testing (time/room/board) | Not addressed | 🔴 Critical |
| Open dataset + reproducible code | Not addressed | 🔴 Critical |
| 5 GHz / ESP32-C5 evaluation | Brief note only | 🟡 Nice-to-have for v1 |
| Uncertainty reporting | Not present | 🔴 Critical |

---

## 1. Measurement Calibration

> **Why it matters**: Without this, you cannot claim ESP32 readings are meaningful. Reviewers will reject immediately.

### 1.1 Board-to-Board RSSI Error
**Protocol**:
1. Place 3 ESP32 boards side-by-side at exactly the same physical point (within 5 cm), same orientation.
2. Measure RSSI to same AP for 10 minutes each (n ≥ 100 samples/board).
3. Compute: mean, std dev, 95% CI, inter-board offset (systematic bias), within-board variance (random noise).
4. Report as: `RSSI_board_i = RSSI_true + bias_i + ε_i` where `bias_i` is board-specific offset.

**Data to report**:
```
Board | Mean RSSI (dBm) | Std Dev | 95% CI         | Bias vs Board 1
ESP1  | -62.3           | ±1.8    | [-65.8, -58.8] | 0 (reference)
ESP2  | -60.1           | ±2.1    | [-64.2, -56.0] | +2.2 dBm
ESP3  | -63.7           | ±1.5    | [-66.6, -60.8] | -1.4 dBm
```

### 1.2 Antenna Orientation Effect
1. Fix probe position, rotate antenna 0°, 45°, 90°, 135°, 180° (5 orientations).
2. Record RSSI at each for 5 minutes.
3. Report orientation-induced variance (expected: 2–6 dBm swing).
4. **Practical conclusion**: define a standard mounting orientation and stick to it for all experiments.

### 1.3 Probe Placement Effect
1. At same AP distance, place probe: on desk surface, 5 cm above desk, 30 cm above desk, floor level.
2. Quantify height and surface effects.
3. Define placement protocol for all subsequent experiments.

### 1.4 Repeated-Measurement Variance
1. Same probe, same location, 3 separate sessions (morning, afternoon, evening).
2. Cross-session variance shows temporal noise independent of fault injection.
3. This becomes your **noise floor** — fault deltas must exceed this.

### 1.5 Accuracy vs. Laptop / Professional Adapter
1. Use laptop Wi-Fi (e.g., Intel AX210) as reference: `airport -I` (macOS) or `iw dev wlan0 scan` (Linux).
2. Measure RSSI simultaneously with ESP32 and laptop at same position.
3. Report systematic offset: ESP32 readings are typically 5–15 dBm lower than laptop adapters.
4. Apply calibration constant in all subsequent analysis.

### 1.6 Timestamp and Packet-Loss Reliability
1. Run NTP on both Pi and ESP32. Log `|t_ESP32 - t_Pi|` continuously.
2. Inject 100 artificial MQTT messages and count received at broker → measure MQTT drop rate.
3. Report max clock drift and message loss rate as system limitations.

---

## 2. Fault-Injection Testbed

> **Why it matters**: Without ground-truth labels on every measurement window, you have monitoring data, not a research dataset.

### 2.1 Fault Class Taxonomy (9 Classes)

| ID | Fault Class | Injection Method | Ground-Truth Label |
|---|---|---|---|
| F0 | Normal operation | Baseline, no injection | `normal` |
| F1 | WAN degradation | `tc netem delay 200ms 50ms loss 5%` on Pi uplink | `wan_degraded` |
| F2 | Router uplink disconnection | Physically unplug WAN port | `wan_down` |
| F3 | DNS failure | Firewall block UDP/TCP port 53 or set bogus DNS | `dns_fail` |
| F4 | AP reboot | Power cycle AP via smart plug or admin panel reboot | `ap_reboot` |
| F5 | Weak signal / obstruction | Move probe behind metal cabinet or add RF absorber | `coverage_weak` |
| F6 | Co-channel contention | Run authorized traffic generator on same channel (iperf2) | `interference` |
| F7 | AP overload | Connect 10–15 clients simultaneously, run HTTP load | `ap_overload` |
| F8 | Local LAN congestion | Run iperf2 between clients on LAN (saturate switch) | `lan_congested` |

### 2.2 Experiment Protocol
```
For each fault class F_i:
  1. Start 5-minute baseline window (normal) → label "normal"
  2. Inject fault at t=0 → label window "F_i"
  3. Run fault for 10 minutes → collect >= 10 measurement cycles per probe
  4. Remove fault → 5-minute recovery window → label "recovery"
  5. Repeat entire sequence 20–30 times across different times of day
  6. Log: fault_class, injection_timestamp, removal_timestamp, run_id
```

### 2.3 tc netem Commands (F1 Implementation)
```bash
# Add WAN degradation on Pi's eth0 uplink
sudo tc qdisc add dev eth0 root netem delay 200ms 50ms loss 5% corrupt 1%

# Remove
sudo tc qdisc del dev eth0 root

# Verify
tc qdisc show dev eth0
```

### 2.4 DNS Failure (F3 Implementation)
```bash
# Block DNS using iptables on Pi
sudo iptables -A OUTPUT -p udp --dport 53 -j DROP
sudo iptables -A OUTPUT -p tcp --dport 53 -j DROP

# Restore
sudo iptables -D OUTPUT -p udp --dport 53 -j DROP
sudo iptables -D OUTPUT -p tcp --dport 53 -j DROP
```

### 2.5 Label Schema (add to InfluxDB)
Every measurement point **must** carry these tags:
```json
{
  "fault_class": "wan_degraded",
  "run_id": "run_042",
  "window_type": "fault",
  "injection_ts": "2026-10-20T09:15:00Z",
  "removal_ts": "2026-10-20T09:25:00Z"
}
```

---

## 3. Cross-Layer Synchronized Measurement

### 3.1 Unified Feature Vector (per 60-second window)

#### Pi Ethernet Layer (wired baseline):
| Feature | Tool | Unit |
|---|---|---|
| `gw_rtt_mean` | ping -c 10 gateway | ms |
| `gw_rtt_std` | ping stddev | ms |
| `gw_loss` | ping | % |
| `inet_rtt_mean` | ping 8.8.8.8 | ms |
| `inet_rtt_std` | ping stddev | ms |
| `inet_loss` | ping | % |
| `dns_latency` | dig timing | ms |
| `http_ttfb` | curl -w "%{time_starttransfer}" | ms |
| `wan_throughput_dl` | speedtest-cli (every 30 min) | Mbps |
| `wan_throughput_ul` | speedtest-cli | Mbps |

#### ESP32 Wi-Fi Layer (per probe, per window):
| Feature | Unit |
|---|---|
| `rssi_mean` | dBm |
| `rssi_std` | dBm |
| `channel` | int |
| `bssid` | string |
| `ap_count_total` | int |
| `ap_count_on_channel` | int |
| `gw_rtt_mean` | ms |
| `gw_rtt_std` | ms |
| `gw_loss` | % |
| `pi_rtt_mean` | ms |
| `pi_rtt_jitter` | ms |
| `pi_loss` | % |
| `throughput_kbps` | kbps |

#### Cross-Layer Derived Features:
| Feature | Description |
|---|---|
| `wifi_wan_rtt_delta` | ESP32 gw_rtt - Pi inet_rtt (isolates Wi-Fi hop overhead) |
| `rssi_rtt_corr` | Rolling correlation of RSSI vs local RTT |
| `probe_health` | ESP32 uptime, reset count, MQTT reconnect count |
| `pi_cpu_temp` | Pi temperature (thermal throttling check) |
| `pi_mem_used_pct` | Memory usage |

### 3.2 Synchronization Protocol
1. Pi as NTP server: `sudo apt install ntp` + configure as stratum-2.
2. ESP32 syncs to Pi NTP at startup and every 30 minutes.
3. Pi timestamps MQTT messages on arrival: `t_pi_rx` tag.
4. Clock drift monitoring: log `|t_esp_sent - t_pi_rx|` per message.
5. Window alignment: aggregate all sources to nearest 60-second boundary using InfluxDB `window()` function.

---

## 4. Classification Models

> **Do not claim diagnosis from RSSI alone** (WiSlow paper finding — RSSI and SINR mislead during interference).

### 4.1 Model Suite (train all four, compare)

| Model | Library | Why |
|---|---|---|
| Rule-based | Pure Python | Interpretable baseline; publishable as standalone |
| Logistic Regression | scikit-learn | Linear baseline, easy feature importance |
| Random Forest | scikit-learn | Non-linear, robust, built-in feature importance |
| XGBoost | xgboost | Strong tabular baseline |
| LSTM (if data >= 2000 windows) | PyTorch or Keras | Temporal patterns (reboot recovery sequence) |

### 4.2 Improved Rule-Based Classifier
```python
def classify_v2(pi, wifi, history, baselines):
    """
    pi: wired metrics dict
    wifi: list of per-probe metric dicts
    history: rolling 10-window history
    baselines: calibrated normal-operation thresholds
    """
    confidence_votes = {}
    
    # Rule 1: WAN fault (requires wired evidence, not just Wi-Fi)
    wan_bad = (pi["inet_loss"] > 3 or 
               pi["inet_rtt_mean"] > 3 * baselines["inet_rtt_mean"])
    all_probes_agree = all(p["pi_loss"] > 2 for p in wifi)
    if wan_bad and all_probes_agree:
        confidence_votes["wan_degraded"] = "high"
    
    # Rule 2: DNS failure (specific pattern)
    if pi["dns_latency"] > 5000 or pi["dns_latency"] == -1:
        if pi["http_ttfb"] > 10000 and pi["gw_rtt_mean"] < 10:
            confidence_votes["dns_fail"] = "high"
    
    # Rule 3: Coverage hole (NOT inferred from RSSI alone)
    for p in wifi:
        if (pi["gw_rtt_mean"] < baselines["gw_rtt_mean"] * 1.2 and  # wired OK
            p["rssi_mean"] < -75 and  # weak signal
            p["gw_rtt_mean"] > 50):   # high local RTT confirms it
            confidence_votes["coverage_weak"] = "high"
    
    # Rule 4: Interference (RSSI >= threshold but degraded — WiSlow-aware)
    for p in wifi:
        if (p["rssi_mean"] > -65 and  # not weak signal
            p["gw_loss"] > 3 and       # actual packet loss
            p["ap_count_on_channel"] >= 4 and  # congested channel
            pi["gw_rtt_mean"] < baselines["gw_rtt_mean"] * 1.5):  # wired fine
            confidence_votes["interference"] = "medium"
    
    # Rule 5: AP overload (temporal, needs history)
    if (len(history) >= 5 and
        all(h["rssi_std"] < 3 for h in history[-5:]) and  # stable signal
        wifi[0]["pi_rtt_mean"] > 2 * baselines["pi_rtt_mean"] and  # degraded perf
        pi["gw_rtt_mean"] < baselines["gw_rtt_mean"] * 1.3):  # wired OK
        confidence_votes["ap_overload"] = "medium"
    
    if not confidence_votes:
        return "inconclusive", "low", []
    
    best = max(confidence_votes, key=lambda k: {"high": 3, "medium": 2, "low": 1}[confidence_votes[k]])
    contributing = [f for f in get_contributing_features(best, pi, wifi)]
    return best, confidence_votes[best], contributing
```

### 4.3 Required Output Format for Every Prediction
```json
{
  "window_id": "2026-10-20T09:15:00Z",
  "predicted_class": "interference",
  "confidence": "medium",
  "contributing_features": ["rssi_mean=-63dBm", "gw_loss=4.2%", "ap_count_on_channel=6"],
  "ground_truth": "interference",
  "correct": true
}
```

### 4.4 Evaluation Metrics (all required)
- Overall accuracy
- Macro-F1 (critical for imbalanced classes)
- Per-class precision, recall, F1
- Confusion matrix (9×9)
- **False ISP-alarm rate** (rate where `normal` or `wifi_fault` is mislabeled as `wan_*`)
- Detection delay (seconds from injection to first correct classification)
- Measurement uncertainty propagation

---

## 5. Generalization Testing (Anti-Overfitting)

> **Never split neighboring samples into train/test** — temporal autocorrelation inflates accuracy.

### 5.1 Test Sets to Create

| Test Set | Description | When to Collect |
|---|---|---|
| Time-separated | Hold out last 20% of data chronologically | After main collection |
| Different room | Place all probes in different room for a full day | After initial experiments |
| Different AP | Temporarily switch to a second router/AP | ~Week 4 |
| Different ESP32 board | Deploy an unseen 4th ESP32; test with model trained on 3 | ~Week 4 |
| Different building | Run 1 day of experiments at a different location | ~Week 5 (aspirational) |

### 5.2 Reporting Template
For each generalization test:
```
Test: Time-separated (chronological split)
Training period: Oct 20 – Nov 5, 2026
Test period:     Nov 6 – Nov 12, 2026
Accuracy: XX%  Macro-F1: XX%
Drop vs. random split: -X pp (shows honest generalization)
```

---

## 6. Open Dataset and Reproducible Code

### 6.1 Repository Structure
```
piprobe/
├── firmware/
│   ├── esp32_probe/          # Arduino / ESP-IDF firmware
│   └── README.md             # Flash instructions
├── pi_scripts/
│   ├── wan_probe.py          # Wired baseline collector
│   ├── fault_injector.py     # Automates tc netem, iptables, etc.
│   └── label_windows.py      # Tags InfluxDB windows with fault class
├── analysis/
│   ├── calibration.ipynb     # Board-to-board RSSI analysis
│   ├── features.py           # Feature extraction from InfluxDB
│   ├── classify_rules.py     # Rule-based classifier
│   ├── classify_ml.py        # LR / RF / XGBoost / LSTM
│   ├── evaluate.py           # Metrics, confusion matrix, ablation
│   └── plots.py              # All paper figures
├── data/
│   ├── schema.md             # InfluxDB measurement schema
│   ├── raw/                  # InfluxDB export (line protocol or CSV)
│   ├── labels.csv            # window_id, fault_class, run_id
│   └── calibration/          # Raw board comparison readings
├── config/
│   ├── docker-compose.yml
│   ├── telegraf.conf
│   ├── mosquitto.conf
│   └── grafana_dashboard.json
├── experiments/
│   └── procedure.md          # Exact step-by-step reproducible procedure
└── paper/
    └── Trinetra_I2MTC2027.pdf
```

### 6.2 Data Release Checklist
- [ ] Raw telemetry in CSV + InfluxDB line protocol format
- [ ] Fault label CSV with timestamps aligned to telemetry
- [ ] Calibration raw readings (board comparison, orientation tests)
- [ ] Configuration files (telegraf, mosquitto, docker-compose)
- [ ] Firmware with build instructions
- [ ] Analysis notebooks with pinned dependencies (`requirements.txt`)
- [ ] `procedure.md`: exact commands to reproduce every experiment
- [ ] `schema.md`: every field, unit, and tag documented

---

## 7. Hardware Plan

### 7.1 Minimum Experiment BOM

| Role | Hardware | Band | Cost (approx. INR) |
|---|---|---|---|
| Wired baseline + server | Raspberry Pi 5, 4 GB | Ethernet | ₹8,000 |
| 2.4 GHz probes | 3× ESP32 WROOM DevKit | 2.4 GHz | ₹900 (×3 at ₹300) |
| 5 GHz probe (optional v1) | ESP32-C5 DevKit | 2.4 + 5 GHz | ₹1,000 |
| AP reboot automation | Smart plug (TP-Link Tapo P100) | — | ₹800 |
| Traffic generator | Own laptop or spare Pi | Both | — |
| **Total** | | | **~₹11,000–12,000** |

### 7.2 iperf Version Note
> ESP32 iPerf example requires **iperf2** (not iperf3).  
> Run `iperf -s` (server) on Pi — NOT `iperf3 -s`.

### 7.3 5 GHz Limitation Statement (for paper)
> "Classic ESP32 WROOM modules support only 2.4 GHz, which covers the dominant legacy band in our test environment. Modern dual-band networks would require ESP32-C5 or equivalent dual-band hardware [Espressif]. We evaluate 2.4 GHz thoroughly and treat 5 GHz extension as future work."

---

## 8. Ablation Study Design

This is the most valuable experimental contribution — complete before adding more features.

| Config | Description | Key Question |
|---|---|---|
| A1: RSSI only | Single feature | Shows RSSI alone is insufficient |
| A2: Wi-Fi metrics only | All ESP32 features, no Pi wired | Proves Wi-Fi-only is limited |
| A3: Wired metrics only | Pi Ethernet only, no ESP32 | Proves wired-only misses coverage faults |
| A4: Wi-Fi + wired (full) | All features | Expected best result |
| A5: Rule-based | Full features, interpretable | Baseline without training |
| A6: Logistic Regression | Full features | Linear ML |
| A7: Random Forest | Full features | Non-linear ML |
| A8: XGBoost | Full features | Gradient boosting ML |

**Key results to prove**:
- `Accuracy(A4) >> Accuracy(A2)` → wired baseline is essential
- `Accuracy(A4) > Accuracy(A3)` → ESP32 probes add value
- False ISP-alarm rate: A3 should be highest (no Wi-Fi context)

---

## 9. Research Questions (Precise Framing)

1. **RQ1**: Can commodity ESP32/Pi probes distinguish WAN, LAN, coverage, interference, and congestion faults with sufficient accuracy for practical diagnosis?
2. **RQ2**: How much does a wired Ethernet Pi baseline reduce the false ISP-alarm rate vs. Wi-Fi-only diagnosis?
3. **RQ3**: How robust is classification across different times of day, rooms, hardware boards, and network environments?
4. **RQ4**: What accuracy–cost trade-off does Trinetra achieve relative to laptop-based professional Wi-Fi survey tools?

---

## 10. Seven-Week Execution Timeline

```
Week 1 (Oct 13–19) — Foundation
  □ Freeze scope: Wi-Fi/WAN diagnosis only (no cellular)
  □ Buy: Pi 5 kit, 3× ESP32 WROOM, 1 smart plug
  □ Flash Pi OS → Docker stack up (Mosquitto, Telegraf, InfluxDB, Grafana)
  □ wan_probe.py running → verify WAN data in Grafana
  □ ESP32 firmware → MQTT data lands in InfluxDB
  □ Define InfluxDB schema with fault_class, run_id tags

Week 2 (Oct 20–26) — Calibration + First Faults
  □ Board-to-board calibration (all 3 ESP32 side-by-side, 10 min each)
  □ Antenna orientation test (5 orientations × 5 min)
  □ Probe placement test (4 heights)
  □ fault_injector.py: implement F1 (tc netem), F2 (unplug), F3 (iptables DNS)
  □ Collect ≥ 20 runs each of F0, F1, F2, F3

Week 3 (Oct 27 – Nov 2) — Full Fault Classes
  □ Implement F4–F8 (smart plug, metal block, iperf2 interference, client flood, LAN congestion)
  □ Collect ≥ 20 runs per class (all 9 classes = 180+ sessions)
  □ Implement cross-layer derived features
  □ NTP sync monitoring: log clock drift per session
  □ Rule-based classifier v2 → end-to-end test per fault class

Week 4 (Nov 3–9) — ML + Generalization Setup
  □ Export features to pandas DataFrame
  □ Train: Logistic Regression, Random Forest, XGBoost
  □ Evaluate on chronological hold-out
  □ Deploy 4th ESP32 (unseen board) for cross-board generalization
  □ Run experiments in second room for cross-room generalization
  □ Begin ablation study (A1–A8)

Week 5 (Nov 10–16) — Ablation + Uncertainty + Figures
  □ Complete all 8 ablation configurations
  □ Report false ISP-alarm rate per configuration
  □ Compute 95% CI for all metrics
  □ Generate: confusion matrices, per-class PR curves, detection delay CDF
  □ RSSI heatmap overlay on floor plan

Week 6 (Nov 17–23) — Dataset + Code Release
  □ Package raw data, labels, configs, firmware → GitHub / Zenodo
  □ Write procedure.md, schema.md
  □ Full pipeline reproducibility test on clean machine
  □ Peer-reproduce one calibration experiment

Week 7 (Nov 24 – Dec 4) — Paper + Submission
  □ Write IEEE I²MTC paper (4–6 pages, 2-column)
      Abstract (150 words) → Introduction → System → Experiments → Conclusion
  □ Supervisor / networking researcher review
  □ Final proofread → submit by Dec 4, 2026
```

---

## 11. Minimum Viable Experiment Gate

Before writing any paper section, verify:

- [ ] Hardware: 1× Pi 5 (Ethernet), 3× ESP32, 1× router/AP, 1× laptop for traffic gen
- [ ] Data: ≥ 20 runs × 9 fault classes = 180+ labeled sessions
- [ ] Calibration: board-to-board, orientation, placement, temporal variance all done
- [ ] Synchronization: NTP drift < 100 ms documented; MQTT loss rate documented
- [ ] Ground truth: **every measurement window** has a `fault_class` label
- [ ] Time-separated test: chronological hold-out evaluated and reported
- [ ] All metrics: accuracy, Macro-F1, per-class PR, confusion matrix, false ISP-alarm rate, detection delay, uncertainty, hardware cost, power consumption, system uptime
- [ ] Ablation: all 8 configurations evaluated
- [ ] Dataset: raw telemetry + labels publicly accessible

---

## 12. Paper Contributions (for Section 1)

1. A **low-cost distributed measurement architecture** using Raspberry Pi 5 + ESP32 probes with a wired Ethernet baseline
2. A **calibrated cross-layer feature set** with uncertainty quantification across multiple boards
3. A **controlled fault-injection methodology** with 9 labeled fault classes and ≥ 20 runs per class
4. An **explainable fault-classification system** reporting predicted cause, confidence, and contributing metrics
5. An **open labeled dataset and reproducible procedure** enabling third-party replication
6. **Evaluation across time, rooms, hardware boards, and network conditions** (generalization study)

---

## 13. Key References

| Paper / Resource | Relevance |
|---|---|
| [WiSlow (INFOCOM 2014)](https://www.cs.columbia.edu/~khkim/papers/kyung_wislow_infocom2014.pdf) | RSSI/SINR mislead during interference → justifies cross-layer approach |
| [Espressif ESP32 Performance](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi-driver/wifi-performance-and-power-save.html) | ~20 Mbps TCP / 30 Mbps UDP hardware bounds |
| [ESP32-C5 (dual-band)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c5/get-started/index.html) | Future work: 5 GHz extension |
| [Espressif iPerf docs](https://docs.espressif.com/projects/esp-techpedia/en/latest/esp-friends/tool-recommendation/iperf.html) | iperf2, not iperf3, required for ESP32 |
| [IEEE I²MTC 2027](https://i2mtc.ieee-ims.org/2027) | Target venue; deadline Dec 4, 2026 |

---

## 14. What NOT to Include in Paper v1

- ❌ Cellular mapping — deferred to future work
- ❌ RSSI-only diagnosis claims — cite WiSlow; run A1 ablation to prove insufficiency
- ❌ Random (non-chronological) train/test split
- ❌ Accuracy without Macro-F1 (classes may be imbalanced)
- ❌ Rule-based OR ML only — compare both
- ❌ Dashboard screenshots as "results" — reviewers want metric tables
- ❌ Numbers without ± or 95% CI

---

*Document created: October 13, 2026*  
*Based on peer-review critique of Trinetra project.*  
*Implementation substrate: existing `Trinetra_Workflow_No_Cellular.md` phases 0–4 remain valid.*
