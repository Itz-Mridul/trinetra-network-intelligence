#!/usr/bin/env python3
"""
Trinetra - Feature Extraction from InfluxDB
Queries InfluxDB 2.x, aggregates raw telemetry into 60-second windows,
computes cross-layer derived features, and exports a labeled CSV
ready for ML training and evaluation.
"""

import os
import sys
import json
import warnings
from datetime import datetime, timezone

import pandas as pd
import numpy as np

# Optional InfluxDB client
try:
    from influxdb_client import InfluxDBClient
    HAS_INFLUX = True
except ImportError:
    HAS_INFLUX = False
    warnings.warn("influxdb-client not installed. Using CSV fallback mode.")

# ── Configuration ──────────────────────────────────────────────────────────────
INFLUX_URL    = os.getenv("INFLUX_URL",   "http://localhost:8086")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG    = os.getenv("INFLUX_ORG",  "piprobe_org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET","telemetry")
WINDOW_SEC    = 60          # classification window in seconds
MIN_SAMPLES   = 4           # minimum ESP32 samples per window
MIN_PI_SAMPLES = 2          # minimum wired-baseline samples per window


def query_influx(start="-7d", stop="now()") -> pd.DataFrame:
    """Query InfluxDB and return raw telemetry as a flat DataFrame."""
    if not HAS_INFLUX:
        raise RuntimeError("influxdb-client not installed. Run: pip3 install influxdb-client")

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()

    flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r["_measurement"] == "network_telemetry")
  |> pivot(rowKey: ["_time", "probe_id", "layer", "room_id", "fault_class", "run_id", "split"],
           columnKey: ["_field"], valueColumn: "_value")
'''
    tables = query_api.query_data_frame(flux)
    client.close()

    if isinstance(tables, list):
        tables = pd.concat(tables, ignore_index=True)

    tables["_time"] = pd.to_datetime(tables["_time"], utc=True)
    return tables


def load_from_csv(csv_path: str) -> pd.DataFrame:
    """Load raw telemetry from a CSV export (fallback without InfluxDB)."""
    df = pd.read_csv(csv_path)
    df["_time"] = pd.to_datetime(df["_time"], utc=True)
    return df


def build_windows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw samples into 60-second windows.
    Returns one row per window with cross-layer derived features.
    """
    # Assign window bins
    df = df.sort_values("_time").copy()
    df["window"] = df["_time"].dt.floor(f"{WINDOW_SEC}s")

    rows = []
    for (window_ts, run_id, fault_class, split), grp in df.groupby(
            ["window", "run_id", "fault_class", "split"], observed=True):

        pi_rows   = grp[grp["layer"] == "wan"]
        wifi_rows = grp[grp["layer"] == "wifi"]

        if len(pi_rows) < MIN_PI_SAMPLES or len(wifi_rows) < MIN_SAMPLES:
            continue  # skip incomplete windows

        def safe_mean(col, src):
            return src[col].mean() if col in src.columns else np.nan
        def safe_std(col, src):
            return src[col].std() if col in src.columns else np.nan
        def safe_max(col, src):
            return src[col].max() if col in src.columns else np.nan

        # ── Wired layer features ──────────────────────────────────────────────
        f = {
            "window_ts":          window_ts.isoformat(),
            "run_id":             run_id,
            "fault_class":        fault_class,
            "split":              split,
            "n_pi_samples":       len(pi_rows),
            "n_wifi_samples":     len(wifi_rows),

            # Pi WAN metrics
            "pi_gw_rtt_mean":     safe_mean("gw_rtt_mean_ms", pi_rows),
            "pi_gw_rtt_std":      safe_std("gw_rtt_std_ms",   pi_rows),
            "pi_gw_loss":         safe_mean("gw_loss_pct",     pi_rows),
            "pi_inet_rtt_mean":   safe_mean("inet_rtt_mean_ms",pi_rows),
            "pi_inet_rtt_std":    safe_std("inet_rtt_std_ms",  pi_rows),
            "pi_inet_loss":       safe_mean("inet_loss_pct",   pi_rows),
            "pi_dns_latency":     safe_mean("dns_latency_ms",  pi_rows),
            "pi_http_ttfb":       safe_mean("http_ttfb_ms",    pi_rows),
            "pi_cpu_temp":        safe_mean("cpu_temp_c",       pi_rows),
            "pi_mem_used":        safe_mean("mem_used_pct",     pi_rows),

            # Wi-Fi layer features (aggregated across all probes in window)
            "wifi_rssi_mean":       safe_mean("rssi_calibrated_dbm", wifi_rows),
            "wifi_rssi_std":        safe_std("rssi_calibrated_dbm",  wifi_rows),
            "wifi_rssi_min":        wifi_rows["rssi_calibrated_dbm"].min() if "rssi_calibrated_dbm" in wifi_rows.columns else np.nan,
            "wifi_gw_rtt_mean":     safe_mean("gw_rtt_mean_ms",      wifi_rows),
            "wifi_gw_rtt_std":      safe_std("gw_rtt_mean_ms",       wifi_rows),
            "wifi_gw_jitter_mean":  safe_mean("gw_rtt_jitter_ms",    wifi_rows),
            "wifi_gw_loss_mean":    safe_mean("gw_loss_pct",         wifi_rows),
            "wifi_gw_loss_max":     safe_max("gw_loss_pct",          wifi_rows),
            "wifi_pi_rtt_mean":     safe_mean("pi_rtt_mean_ms",      wifi_rows),
            "wifi_pi_jitter_mean":  safe_mean("pi_rtt_jitter_ms",    wifi_rows),
            "wifi_pi_loss_mean":    safe_mean("pi_loss_pct",         wifi_rows),
            "wifi_ap_on_channel":   safe_mean("ap_count_on_channel", wifi_rows),
            "wifi_tput_kbps":       safe_mean("tput_kbps",           wifi_rows),
            "wifi_reconnects":      safe_max("reconnect_count",       wifi_rows),
        }

        # ── Cross-layer derived features ──────────────────────────────────────
        if not np.isnan(f["wifi_gw_rtt_mean"]) and not np.isnan(f["pi_gw_rtt_mean"]):
            f["rtt_hop_delta"] = f["wifi_gw_rtt_mean"] - f["pi_gw_rtt_mean"]
        else:
            f["rtt_hop_delta"] = np.nan

        if not np.isnan(f["wifi_gw_loss_mean"]) and not np.isnan(f["pi_gw_loss"]):
            f["loss_hop_delta"] = f["wifi_gw_loss_mean"] - f["pi_gw_loss"]
        else:
            f["loss_hop_delta"] = np.nan

        # RSSI-RTT correlation signal: strong RSSI with high RTT indicates interference/contention
        if not np.isnan(f["wifi_rssi_mean"]) and not np.isnan(f["wifi_gw_rtt_mean"]):
            # Normalize: Strong RSSI (-45dBm) + high RTT → larger value → interference fingerprint
            # Weak RSSI (-85dBm) + high RTT → smaller value → path loss / coverage hole
            f["rssi_rtt_index"] = (f["wifi_gw_rtt_mean"] / max(1.0, abs(f["wifi_rssi_mean"]))) * 100.0
        else:
            f["rssi_rtt_index"] = np.nan

        rows.append(f)

    result = pd.DataFrame(rows)
    print(f"[Features] Extracted {len(result)} windows from {len(df)} raw samples.")
    return result


def save_features(df: pd.DataFrame, out_path: str):
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[Features] Saved to {out_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trinetra Feature Extraction")
    parser.add_argument("--source", choices=["influxdb", "csv"], default="influxdb")
    parser.add_argument("--csv",  default="data/raw/telemetry.csv",
                        help="Input CSV path when --source=csv")
    parser.add_argument("--out",  default="data/features.csv")
    parser.add_argument("--start", default="-7d", help="InfluxDB range start")
    args = parser.parse_args()

    if args.source == "influxdb":
        raw = query_influx(start=args.start)
    else:
        raw = load_from_csv(args.csv)

    windows = build_windows(raw)
    save_features(windows, args.out)
    print(windows[["window_ts", "fault_class", "wifi_rssi_mean",
                   "pi_inet_rtt_mean", "rtt_hop_delta"]].tail(10))
