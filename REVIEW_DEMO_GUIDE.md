# Trinetra: 4-Day Project Review & Prototype Demo Runbook

**Goal:** Deliver a flawless live demonstration of the Trinetra prototype to your project review panel / supervisor.

---

## 1. The 5-Minute Live Demonstration Script

Follow this exact sequence in front of the reviewers. Have two windows open side-by-side:
- **Left Window:** Grafana Dashboard (`http://localhost:3000` or `http://<PI_IP>:3000`)
- **Right Window:** Terminal running `python3 demo_runner.py` (or real hardware)

### Minute 0:00 – 1:00: Problem & The "Wired Truth Anchor"
> *"Good morning professors. When an end-user experiences poor internet, they immediately blame either their ISP or their Wi-Fi router. However, commercial survey tools and simple speedtests cannot distinguish whether the bottleneck is at the local Wi-Fi hop, co-channel interference, or upstream ISP transit.*
>
> *PiProbe solves this by deploying a two-tier architecture: a Raspberry Pi 5 connected over Ethernet as a **clean wired baseline** (measuring pure gateway and ISP latency), and cheap distributed ESP32 microcontrollers in different rooms as **wireless edge probes**."*

### Minute 1:00 – 2:30: Normal Operation vs. Wi-Fi Coverage Hole
1. Show Grafana: all lines green, low latency (< 15 ms).
2. Type `3` in the demo terminal to inject **F5: Wi-Fi Coverage Hole**:
3. Type `d` in the terminal to trigger the live classifier.
> *"Watch probe 2 in the bedroom: its calibrated RSSI drops below -80 dBm, and local RTT spikes to 65 ms. But look at the Pi's wired baseline: gateway and internet RTT remain perfectly flat. Our classifier instantly diagnoses this as a **Coverage Hole with High Confidence**, and isolates the fault to the bedroom without falsely blaming the ISP."*

### Minute 2:30 – 3:45: The "WiSlow" Interference Test (The Impressive Academic Point)
1. Type `4` in the demo terminal to inject **F6: Co-channel Interference**:
2. Type `d` to run the classifier.
> *"Here is why RSSI alone is misleading, as shown in the IEEE WiSlow research: probe 1's signal strength is strong at -60 dBm. A naive smartphone app would say 'Wi-Fi is excellent'. But packet loss is 10% and jitter has quadrupled due to competing channel traffic. Because the Pi's wired link shows 0% loss, our classifier correctly identifies **Co-Channel Interference**."*

### Minute 3:45 – 5:00: Controlled WAN Impairment & Questions
1. Type `1` in the terminal to inject **F1: WAN Degradation**:
2. Type `d` to run the classifier.
> *"Now we simulate ISP transit degradation using `tc netem`. Notice that the Pi's external RTT jumps to 240 ms, but local gateway ping remains under 2 ms. The classifier immediately attributes this to **WAN/ISP Degradation** with full causal transparency."*

---

## 2. Top 5 Questions Reviewers Will Ask (And What to Answer)

### Q1: *"Why did you use ESP32s instead of just using laptops or phones?"*
**Answer:**  
> *"Laptops cost $500–1000 each and consume 30–65W, making 24/7 multi-room deployment impractical. ESP32s cost less than $3 each and consume under 0.8W. Furthermore, phone OSes randomize MAC addresses, throttle background Wi-Fi scans, and do not provide raw radio telemetry."*

### Q2: *"ESP32 RSSI is notorious for board-to-board variation and antenna directivity. How can you trust it?"*
**Answer:**  
> *"We do not rely on raw RSSI. First, we conducted side-by-side calibration experiments to calculate a fixed board offset ($\text{bias}_i$) for each probe. Second, per the IEEE WiSlow findings, we never diagnose from RSSI alone: our classifier requires cross-layer corroboration (local RTT, packet loss, and the wired Pi baseline) before making a causal attribution."*

### Q3: *"Is this just an engineering project with a Grafana dashboard?"*
**Answer:**  
> *"The dashboard is purely an operational tool. The core research contribution is the **calibrated cross-layer fault classification algorithm**, the **controlled fault-injection methodology with 9 ground-truth classes**, and our ablation study proving how much a wired baseline reduces false ISP alarms."*

### Q4: *"Why do you have an explicit 'Inconclusive' class?"*
**Answer:**  
> *"In real-world networks, noise and transient spikes can create ambiguous signatures. Standard ML models force a false classification when uncertain. PiProbe uses a rejection threshold so it abstains when confidence is low, which prevents false alarms."*

### Q5: *"Can your system handle 5 GHz networks?"*
**Answer:**  
> *"Classic ESP32-WROOM boards are 2.4 GHz only, which covers legacy and IoT bands. For 5 GHz dual-band coverage, our architecture natively supports the newly released ESP32-C5 SoC, and we treat 5 GHz as an expansion module."*

---

## 3. Checklist for Review Day (T-Minus 30 Minutes)

- [ ] Pi 5 powered via official 27W supply, Ethernet cable firmly plugged in.
- [ ] Docker containers running: `docker compose ps` shows `mosquitto`, `influxdb`, `telegraf`, `grafana` healthy.
- [ ] Terminal window open with `demo_runner.py` tested.
- [ ] Browser open to Grafana dashboard (`piprobe-live-dash`), set to auto-refresh every **5s**.
- [ ] ESP32 probe powered and displaying Wi-Fi connected on Serial Monitor (or demo runner in fallback simulation mode).
- [ ] Slide deck loaded with the 3 key slides (Problem, Architecture, Results).
