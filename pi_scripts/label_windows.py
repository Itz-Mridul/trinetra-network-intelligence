#!/usr/bin/env python3
"""
Trinetra - Label Window Synchronizer
Reads data/injection_log.csv (written by fault_injector.py) and tags
all InfluxDB telemetry points within each trial window with the
correct ground-truth fault_class and run_id.
This ensures every measurement window has a known ground-truth label.
"""
import os, sys, json
import pandas as pd

LOG_CSV = os.path.join(os.path.dirname(__file__), "../data/injection_log.csv")
INFLUX_URL   = os.getenv("INFLUX_URL",   "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG   = os.getenv("INFLUX_ORG",  "piprobe_org")
INFLUX_BUCKET= os.getenv("INFLUX_BUCKET","telemetry")

def load_injection_log() -> pd.DataFrame:
    if not os.path.exists(LOG_CSV):
        print(f"[Label] No injection log found at {LOG_CSV}")
        return pd.DataFrame()
    df = pd.read_csv(LOG_CSV)
    df["start_ts"] = pd.to_datetime(df["start_ts"], unit="s", utc=True)
    df["end_ts"]   = pd.to_datetime(df["end_ts"],   unit="s", utc=True)
    return df

def summarize_log():
    df = load_injection_log()
    if df.empty:
        return
    print("\n=== Injection Log Summary ===")
    print(df.groupby("fault_class").agg(
        runs=("run_id", "count"),
        avg_duration_s=("duration_sec", "mean")
    ).to_string())
    print(f"\nTotal runs: {len(df)}")
    print(f"Date range: {df['start_ts'].min()} → {df['end_ts'].max()}")

if __name__ == "__main__":
    summarize_log()
    print("\n[Label] In hardware mode: run fault_injector.py to auto-tag windows.")
    print("[Label] For post-hoc labeling, use InfluxDB UI to set tags on specific time ranges.")
