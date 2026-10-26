#!/usr/bin/env python3
"""
Trinetra - Explainable Cross-Layer Rule-Based Classifier (WiSlow-Aware)
Evaluates 60-second time-series windows of synchronized wired and wireless metrics.
Attributes root causes into:
  - normal
  - wan_degraded
  - wan_down
  - dns_fail
  - coverage_weak
  - interference
  - ap_overload
  - lan_congested
  - probe_fault
  - inconclusive (abstains when evidence is insufficient)
"""

import json

def classify_window(wired_sample, wifi_samples, baselines=None):
    """
    wired_sample: dict of Pi wired baseline metrics (gw_rtt, inet_rtt, dns, loss)
    wifi_samples: list of dicts from distributed ESP32 probes in this window
    baselines: dict of normal operating medians (inet_rtt_base, gw_rtt_base, etc.)
    
    Returns: (predicted_fault, confidence, contributing_metrics)
    """
    if baselines is None:
        baselines = {
            "inet_rtt_base": 15.0,
            "gw_rtt_base": 2.0,
            "wifi_gw_rtt_base": 6.0,
            "dns_latency_base": 25.0
        }

    votes = []

    # Check Probe Fault (Probe silence or high reconnect count)
    if not wifi_samples:
        return "probe_fault", "high", ["No Wi-Fi probe telemetry received in this window"]

    for probe in wifi_samples:
        if probe.get("reconnect_count", 0) > 3 or probe.get("gw_loss_pct", 0) == 100.0:
            if wired_sample.get("inet_loss_pct", 0) == 0:
                votes.append(("probe_fault", "medium", [f"{probe['probe_id']} dropped connection, wired link healthy"]))

    # Rule 1: DNS Failure (Port 53 failure while IP routing is healthy)
    dns_lat = wired_sample.get("dns_latency_ms", -1)
    if (dns_lat > 2000 or dns_lat == -1) and wired_sample.get("inet_loss_pct", 0) < 5:
        return "dns_fail", "high", [f"dns_latency={dns_lat}ms", f"inet_loss={wired_sample.get('inet_loss_pct')}%"]

    # Rule 2: Total WAN Down. Prefer multi-target HTTPS evidence over ICMP,
    # because mobile carriers and public hosts commonly filter ping.
    https_success = wired_sample.get("wan_http_success_pct")
    download_mbps = wired_sample.get("wan_tput_dl_mbps")
    if https_success is not None:
        if https_success < 34 and wired_sample.get("gw_loss_pct", 0) < 5:
            return "wan_down", "high", [
                f"Only {https_success}% of HTTPS targets responded",
                "Local gateway path remained responsive",
            ]
    elif wired_sample.get("inet_loss_pct", 0) > 80 and wired_sample.get("gw_loss_pct", 0) == 0:
        return "inconclusive", "low", [
            "ICMP Internet loss exceeded 80%, but multi-target HTTPS evidence is missing",
        ]

    # Rule 3: WAN / ISP Degradation (Wired latency/jitter spikes across external destinations)
    inet_rtt = wired_sample.get("inet_rtt_mean_ms", 0)
    inet_loss = wired_sample.get("inet_loss_pct", 0)
    https_degraded = https_success is not None and https_success < 80
    download_degraded = download_mbps is not None and download_mbps >= 0 and download_mbps < 5.0
    if (https_degraded or download_degraded or (https_success is None and (inet_loss > 4.0 or inet_rtt > 3.0 * baselines["inet_rtt_base"]))) and wired_sample.get("gw_rtt_mean_ms", 0) < 5.0:
        # Verify Wi-Fi probes also see high external RTT or packet loss
        return "wan_degraded", "high", [
            f"pi_inet_rtt={inet_rtt}ms (baseline {baselines['inet_rtt_base']}ms)",
            f"pi_inet_loss={inet_loss}%",
            f"https_success={https_success}%",
            f"download_mbps={download_mbps}",
            f"pi_gw_rtt={wired_sample.get('gw_rtt_mean_ms')}ms"
        ]

    # Rule 4: Wi-Fi Coverage Hole (Low RSSI + high local RTT, wired is fine)
    weak_probes = []
    for probe in wifi_samples:
        rssi = probe.get("rssi_calibrated_dbm", probe.get("rssi_raw_dbm", -99))
        local_rtt = probe.get("gw_rtt_mean_ms", 0)
        if rssi < -75 and local_rtt > 20.0 and wired_sample.get("gw_rtt_mean_ms", 0) < 5.0:
            weak_probes.append((probe["probe_id"], rssi, local_rtt))
    if weak_probes:
        contributors = [f"{p[0]}: rssi={p[1]}dBm, local_rtt={p[2]}ms" for p in weak_probes]
        return "coverage_weak", "high", contributors

    # Rule 5: Wi-Fi Interference / Contention (WiSlow Rule: Good RSSI but elevated loss/jitter + many APs)
    interfered_probes = []
    for probe in wifi_samples:
        rssi = probe.get("rssi_calibrated_dbm", probe.get("rssi_raw_dbm", -99))
        local_loss = probe.get("gw_loss_pct", 0)
        local_jitter = probe.get("gw_rtt_jitter_ms", 0)
        ap_on_ch = probe.get("ap_count_on_channel", 0)

        # WiSlow finding: RSSI >= -65dBm but throughput/loss degraded
        if rssi >= -68 and (local_loss > 3.0 or local_jitter > 10.0) and ap_on_ch >= 3:
            interfered_probes.append((probe["probe_id"], rssi, local_loss, local_jitter, ap_on_ch))
    if interfered_probes:
        contributors = [f"{p[0]}: rssi={p[1]}dBm, loss={p[2]}%, jitter={p[3]}ms, ch_co_channel={p[4]}" for p in interfered_probes]
        return "interference", "medium", contributors

    # Rule 6: AP Overload (All probes experience elevated local latency, but wired LAN is pristine)
    if len(wifi_samples) >= 2:
        all_probes_slow = all(p.get("gw_rtt_mean_ms", 0) > 2.5 * baselines["wifi_gw_rtt_base"] for p in wifi_samples)
        if all_probes_slow and wired_sample.get("gw_rtt_mean_ms", 0) < 3.0:
            return "ap_overload", "medium", ["All distributed probes show >2.5x local RTT inflation", "Wired gateway RTT normal"]

    # Rule 7: LAN Congestion (Both wired Pi and ESP32 probes experience high gateway latency)
    if wired_sample.get("gw_rtt_mean_ms", 0) > 4.0 * baselines["gw_rtt_base"]:
        return "lan_congested", "high", [f"pi_gw_rtt={wired_sample.get('gw_rtt_mean_ms')}ms (baseline {baselines['gw_rtt_base']}ms)"]

    # Fallback to normal if everything is in spec
    if wired_sample.get("inet_loss_pct", 0) == 0 and wired_sample.get("gw_loss_pct", 0) == 0:
        all_wifi_healthy = all(p.get("gw_loss_pct", 0) == 0 for p in wifi_samples)
        if all_wifi_healthy:
            return "normal", "high", ["All wired and wireless KPIs within nominal baseline"]

    # Rule 8: Probe Fault (Collected votes for disconnected or isolated probe failures)
    if votes:
        reasons = [r for v in votes for r in v[2]]
        return "probe_fault", "medium", reasons

    return "inconclusive", "low", ["Ambiguous cross-layer signature: insufficient evidence for causal attribution"]

if __name__ == "__main__":
    # Test with synthetic test case: Wi-Fi interference vs WAN fault
    sample_wired = {
        "gw_rtt_mean_ms": 1.2,
        "inet_rtt_mean_ms": 14.5,
        "inet_loss_pct": 0.0,
        "dns_latency_ms": 18.0
    }
    sample_wifi = [{
        "probe_id": "esp_probe_1",
        "rssi_calibrated_dbm": -61.0,
        "gw_rtt_mean_ms": 14.8,
        "gw_rtt_jitter_ms": 12.2,
        "gw_loss_pct": 4.5,
        "ap_count_on_channel": 5
    }]

    verdict, conf, reasons = classify_window(sample_wired, sample_wifi)
    print(f"Classification Result: {verdict.upper()} (Confidence: {conf})")
    print(f"Contributing Metrics: {reasons}")
