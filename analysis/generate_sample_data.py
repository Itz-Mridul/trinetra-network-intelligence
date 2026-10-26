#!/usr/bin/env python3
"""
Trinetra - Synthetic Sample Data Generator
Generates realistic multi-fault labeled window features for ML classification
and ablation testing without requiring prior physical trials.
"""

import os
import numpy as np
import pandas as pd

FEATURE_COLS = [
    "pi_gw_rtt_mean", "pi_gw_rtt_std", "pi_gw_loss",
    "pi_inet_rtt_mean", "pi_inet_rtt_std", "pi_inet_loss",
    "pi_dns_latency", "pi_http_ttfb",
    "wifi_rssi_mean", "wifi_rssi_std", "wifi_rssi_min",
    "wifi_gw_rtt_mean", "wifi_gw_rtt_std", "wifi_gw_jitter_mean",
    "wifi_gw_loss_mean", "wifi_gw_loss_max",
    "wifi_pi_rtt_mean", "wifi_pi_jitter_mean", "wifi_pi_loss_mean",
    "wifi_ap_on_channel", "wifi_tput_kbps", "wifi_reconnects",
    "rtt_hop_delta", "loss_hop_delta", "rssi_rtt_index",
]

CLASSES = [
    "normal", "wan_degraded", "wan_down", "dns_fail",
    "coverage_weak", "interference", "ap_overload", "lan_congested", "probe_fault"
]

def generate_sample_features(num_samples: int = 720, random_state: int = 42) -> pd.DataFrame:
    """Generate synthetic window features with realistic cross-layer distributions."""
    np.random.seed(random_state)
    samples_per_class = max(10, num_samples // len(CLASSES))
    rows = []

    for c in CLASSES:
        for i in range(samples_per_class):
            # Base nominal values (healthy system)
            # Wired Pi metrics
            pi_gw_rtt   = float(np.random.normal(1.8, 0.4))
            pi_gw_rtt_s = float(np.random.uniform(0.1, 0.5))
            pi_gw_loss  = 0.0
            pi_inet_rtt = float(np.random.normal(16.0, 2.5))
            pi_inet_s   = float(np.random.uniform(0.8, 3.0))
            pi_inet_l   = 0.0
            pi_dns      = float(np.random.normal(22.0, 4.0))
            pi_http     = float(np.random.normal(45.0, 8.0))

            # Wi-Fi ESP32 probe metrics
            w_rssi_mean = float(np.random.normal(-48.0, 4.0))
            w_rssi_std  = float(np.random.uniform(0.5, 2.0))
            w_rssi_min  = w_rssi_mean - float(np.random.uniform(1.0, 5.0))
            w_gw_rtt    = float(np.random.normal(6.5, 1.5))
            w_gw_rtt_s  = float(np.random.uniform(0.8, 2.5))
            w_gw_jit    = float(np.random.uniform(1.0, 3.0))
            w_gw_loss   = 0.0
            w_gw_loss_m = 0.0
            w_pi_rtt    = float(np.random.normal(7.2, 1.8))
            w_pi_jit    = float(np.random.uniform(1.2, 3.5))
            w_pi_loss   = 0.0
            w_ap_ch     = int(np.random.choice([1, 2]))
            w_tput      = float(np.random.normal(4800.0, 400.0))
            w_reconn    = 0

            # Fault injections
            if c == "wan_degraded":
                pi_inet_rtt = float(np.random.normal(210.0, 35.0))
                pi_inet_s   = float(np.random.normal(45.0, 10.0))
                pi_inet_l   = float(np.random.uniform(4.0, 15.0))
                pi_http     = float(np.random.normal(320.0, 50.0))

            elif c == "wan_down":
                pi_inet_l   = 100.0
                pi_inet_rtt = 999.0
                pi_dns      = 3000.0
                pi_http     = 5000.0

            elif c == "dns_fail":
                pi_dns      = float(np.random.uniform(2500.0, 4500.0))
                pi_http     = float(np.random.uniform(2800.0, 5000.0))

            elif c == "coverage_weak":
                w_rssi_mean = float(np.random.normal(-82.0, 3.0))
                w_rssi_min  = w_rssi_mean - float(np.random.uniform(3.0, 8.0))
                w_gw_rtt    = float(np.random.normal(38.0, 10.0))
                w_gw_jit    = float(np.random.uniform(12.0, 25.0))
                w_gw_loss   = float(np.random.uniform(8.0, 25.0))
                w_gw_loss_m = w_gw_loss + float(np.random.uniform(5.0, 15.0))
                w_tput      = float(np.random.normal(650.0, 120.0))

            elif c == "interference":
                # Good RSSI, but high channel contention, jitter, and packet loss
                w_rssi_mean = float(np.random.normal(-54.0, 3.0))
                w_ap_ch     = int(np.random.choice([4, 5, 6]))
                w_gw_rtt    = float(np.random.normal(28.0, 8.0))
                w_gw_jit    = float(np.random.uniform(18.0, 35.0))
                w_gw_loss   = float(np.random.uniform(5.0, 18.0))
                w_gw_loss_m = w_gw_loss + 10.0
                w_tput      = float(np.random.normal(1200.0, 250.0))

            elif c == "ap_overload":
                w_rssi_mean = float(np.random.normal(-50.0, 2.5))
                w_gw_rtt    = float(np.random.normal(32.0, 6.0))
                w_gw_jit    = float(np.random.uniform(8.0, 15.0))
                w_gw_loss   = float(np.random.uniform(3.0, 10.0))
                w_tput      = float(np.random.normal(900.0, 150.0))

            elif c == "lan_congested":
                pi_gw_rtt   = float(np.random.normal(18.0, 4.0))
                pi_gw_rtt_s = float(np.random.uniform(4.0, 8.0))
                pi_inet_rtt = float(np.random.normal(38.0, 6.0))
                w_gw_rtt    = float(np.random.normal(26.0, 5.0))

            elif c == "probe_fault":
                w_reconn    = int(np.random.choice([3, 4, 6]))
                w_gw_loss   = 100.0
                w_gw_rtt    = 999.0

            # Derived cross-layer features
            rtt_hop_delta  = w_gw_rtt - pi_gw_rtt
            loss_hop_delta = w_gw_loss - pi_gw_loss
            # Higher index indicates elevated delay relative to strong signal (interference/contention)
            rssi_rtt_index = (w_gw_rtt / max(1.0, abs(w_rssi_mean))) * 100.0

            # Chronological split assignment: 70% train, 30% test across temporal buckets
            split = "train" if (i < int(samples_per_class * 0.7)) else "test_time"

            row = {
                "pi_gw_rtt_mean": round(pi_gw_rtt, 3),
                "pi_gw_rtt_std":  round(pi_gw_rtt_s, 3),
                "pi_gw_loss":     round(pi_gw_loss, 2),
                "pi_inet_rtt_mean": round(pi_inet_rtt, 3),
                "pi_inet_rtt_std":  round(pi_inet_s, 3),
                "pi_inet_loss":     round(pi_inet_l, 2),
                "pi_dns_latency": round(pi_dns, 2),
                "pi_http_ttfb":   round(pi_http, 2),
                "wifi_rssi_mean": round(w_rssi_mean, 2),
                "wifi_rssi_std":  round(w_rssi_std, 2),
                "wifi_rssi_min":  round(w_rssi_min, 2),
                "wifi_gw_rtt_mean": round(w_gw_rtt, 3),
                "wifi_gw_rtt_std":  round(w_gw_rtt_s, 3),
                "wifi_gw_jitter_mean": round(w_gw_jit, 3),
                "wifi_gw_loss_mean": round(w_gw_loss, 2),
                "wifi_gw_loss_max":  round(w_gw_loss_m, 2),
                "wifi_pi_rtt_mean":  round(w_pi_rtt, 3),
                "wifi_pi_jitter_mean": round(w_pi_jit, 3),
                "wifi_pi_loss_mean": round(w_pi_loss, 2),
                "wifi_ap_on_channel": w_ap_ch,
                "wifi_tput_kbps": round(w_tput, 1),
                "wifi_reconnects": w_reconn,
                "rtt_hop_delta":  round(rtt_hop_delta, 3),
                "loss_hop_delta": round(loss_hop_delta, 2),
                "rssi_rtt_index": round(rssi_rtt_index, 3),
                "fault_class": c,
                "split": split,
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    return df


def generate_features_csv(output_path: str, num_samples: int = 720):
    """Generate and write synthetic features CSV to file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = generate_sample_features(num_samples=num_samples)
    df.to_csv(output_path, index=False)
    print(f"[Sample Data] Generated {len(df)} synthetic feature records across {len(CLASSES)} classes → {output_path}")


if __name__ == "__main__":
    generate_features_csv("data/features.csv")
