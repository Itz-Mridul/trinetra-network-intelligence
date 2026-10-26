#!/usr/bin/env python3
"""
Trinetra - Calibration Analysis Script
Quantifies board-to-board RSSI bias, antenna orientation variance,
and probe placement effects from calibration experiment data.
Outputs calibration offsets for the CALIBRATION_BIAS constant in firmware.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

# ── Calibration Data Schema ───────────────────────────────────────────────────
# CSV columns expected:
# timestamp, probe_id, rssi_raw_dbm, orientation_deg, height_cm, session_id
# session_id: "colocation_test" | "orientation_test" | "placement_test" | "temporal_test"

CALIBRATION_CSV = os.path.join(os.path.dirname(__file__), "../data/calibration/cal_data.csv")
OUT_DIR         = os.path.join(os.path.dirname(__file__), "../data/calibration")


def compute_gum_uncertainty(values: np.ndarray, k: float = 2.0) -> dict:
    """
    Compute GUM (ISO/IEC Guide 98-3) combined uncertainty.
    k=2 gives 95% confidence expanded uncertainty U.
    Returns dict: mean, std, u_c (standard), U (expanded), ci_lower, ci_upper
    """
    values = np.asarray(values, dtype=float)
    n    = len(values)
    if n == 0:
        raise ValueError("At least one calibration value is required")
    mean = np.mean(values)
    sample_std = np.std(values, ddof=1) if n > 1 else 0.0
    u_c  = sample_std / np.sqrt(n)   # Type A standard uncertainty
    U    = k * u_c                                 # Expanded uncertainty
    return {
        "mean":     round(mean, 3),
        "std":      round(sample_std, 3),
        "n":        n,
        "u_c":      round(u_c, 4),
        "U":        round(U, 4),
        "ci_lower": round(mean - U, 3),
        "ci_upper": round(mean + U, 3),
    }


def board_to_board_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-board statistics and bias relative to reference board."""
    sub = df[df["session_id"] == "colocation_test"].copy()
    if sub.empty:
        print("[CAL] No colocation_test data found. Skipping board-to-board analysis.")
        return pd.DataFrame()

    reference_board = sorted(sub["probe_id"].unique())[0]
    ref_mean = sub[sub["probe_id"] == reference_board]["rssi_raw_dbm"].mean()

    rows = []
    for probe, grp in sub.groupby("probe_id"):
        vals = grp["rssi_raw_dbm"].values
        stats = compute_gum_uncertainty(vals)
        stats["probe_id"] = probe
        stats["bias_vs_ref_dbm"] = round(stats["mean"] - ref_mean, 3)
        # Sign correction: if board reads +2.3 dBm above reference, firmware must add -2.3 dBm to equalize
        stats["firmware_calibration_bias_dbm"] = round(ref_mean - stats["mean"], 3)
        stats["is_reference"] = (probe == reference_board)
        rows.append(stats)

    result = pd.DataFrame(rows).set_index("probe_id")
    print("\n=== Board-to-Board RSSI Calibration Results ===")
    print(result.to_string())
    print(f"\n[CAL] Reference board: {reference_board} (bias = 0.000 dBm)")
    print("[CAL] Use 'firmware_calibration_bias_dbm' (ref_mean - board_mean) as CALIBRATION_BIAS in esp32_probe.ino")
    return result


def orientation_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Quantify antenna orientation effect on RSSI."""
    sub = df[df["session_id"] == "orientation_test"].copy()
    if sub.empty:
        print("[CAL] No orientation_test data. Skipping.")
        return pd.DataFrame()

    rows = []
    for angle, grp in sub.groupby("orientation_deg"):
        stats = compute_gum_uncertainty(grp["rssi_raw_dbm"].values)
        stats["orientation_deg"] = angle
        rows.append(stats)

    result = pd.DataFrame(rows).set_index("orientation_deg").sort_index()
    swing = result["mean"].max() - result["mean"].min()
    print(f"\n=== Antenna Orientation Effect (RSSI swing: {swing:.1f} dBm) ===")
    print(result[["mean", "std", "U", "ci_lower", "ci_upper"]].to_string())
    best_angle = result["mean"].idxmax()
    print(f"[CAL] Best mounting angle: {best_angle}° — use this for all probes.")
    return result


def temporal_variance_analysis(df: pd.DataFrame) -> dict:
    """Compute cross-session temporal noise floor (measurement noise floor for fault detection)."""
    sub = df[df["session_id"] == "temporal_test"].copy()
    if sub.empty:
        print("[CAL] No temporal_test data. Skipping.")
        return {}

    sessions = sub.groupby("session_id")
    vals = sub["rssi_raw_dbm"].values
    stats = compute_gum_uncertainty(vals)
    print(f"\n=== Temporal Variance (Noise Floor) ===")
    print(f"  Overall: mean={stats['mean']} dBm, std={stats['std']} dBm, U(k=2)={stats['U']} dBm")
    print(f"  [CAL] Fault-induced RSSI deltas must exceed {stats['U']:.1f} dBm to be distinguishable from noise.")
    return stats


def generate_sample_calibration_data():
    """Generate synthetic calibration data for testing before real hardware is assembled."""
    np.random.seed(42)
    rows = []
    
    # Board-to-board colocation test (3 boards, 200 samples each)
    biases = {"esp_probe_1": 0.0, "esp_probe_2": +2.3, "esp_probe_3": -1.8}
    for probe, bias in biases.items():
        for _ in range(200):
            rows.append({
                "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                "probe_id": probe,
                "rssi_raw_dbm": round(-62.0 + bias + np.random.normal(0, 1.5), 1),
                "orientation_deg": 0,
                "height_cm": 30,
                "session_id": "colocation_test"
            })
    
    # Orientation test (1 board, 5 angles x 100 samples)
    orientation_effects = {0: 0.0, 45: -1.2, 90: -3.5, 135: -2.1, 180: -1.0}
    for angle, effect in orientation_effects.items():
        for _ in range(100):
            rows.append({
                "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                "probe_id": "esp_probe_1",
                "rssi_raw_dbm": round(-62.0 + effect + np.random.normal(0, 1.2), 1),
                "orientation_deg": angle,
                "height_cm": 30,
                "session_id": "orientation_test"
            })
    
    # Temporal test (3 sessions across day)
    for _ in range(300):
        rows.append({
            "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
            "probe_id": "esp_probe_1",
            "rssi_raw_dbm": round(-62.0 + np.random.normal(0, 2.1), 1),
            "orientation_deg": 0,
            "height_cm": 30,
            "session_id": "temporal_test"
        })
    
    df = pd.DataFrame(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(CALIBRATION_CSV, index=False)
    print(f"[CAL] Generated {len(df)} synthetic calibration samples → {CALIBRATION_CSV}")
    return df


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Trinetra Calibration Analysis")
    parser.add_argument("--generate-sample", action="store_true",
                        help="Generate synthetic calibration data for testing")
    parser.add_argument("--csv", default=CALIBRATION_CSV)
    args = parser.parse_args()

    if args.generate_sample or not os.path.exists(args.csv):
        print("[CAL] Generating synthetic calibration data (replace with real measurements)...")
        df = generate_sample_calibration_data()
    else:
        df = pd.read_csv(args.csv)
        print(f"[CAL] Loaded {len(df)} calibration samples from {args.csv}")

    board_results    = board_to_board_analysis(df)
    orientation_res  = orientation_analysis(df)
    noise_floor      = temporal_variance_analysis(df)

    # Save calibration offsets
    if not board_results.empty:
        offsets = board_results[["firmware_calibration_bias_dbm", "U"]].copy()
        offsets.columns = ["calibration_bias_dbm", "expanded_uncertainty_U_k2"]
        out = os.path.join(OUT_DIR, "calibration_offsets.csv")
        offsets.to_csv(out)
        print(f"\n[CAL] Calibration offsets saved to {out}")
        print("[CAL] Copy these values into CALIBRATION_BIAS in each board's firmware.")

    print("\n=== Calibration Analysis Complete ===")


if __name__ == "__main__":
    main()
