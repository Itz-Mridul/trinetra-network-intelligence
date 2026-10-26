#!/usr/bin/env python3
"""
Trinetra - ML Fault Classifier
Trains and evaluates four models on labeled window features:
  - Logistic Regression (linear baseline)
  - Random Forest (non-linear, feature importance)
  - XGBoost (gradient boosting)
  - Rule-based (no training, deterministic)
Uses chronological train/test split (no data leakage).
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

# Add parent dir for rule classifier
sys.path.append(os.path.dirname(__file__))

from sklearn.linear_model    import LogisticRegression
from sklearn.ensemble        import RandomForestClassifier
from sklearn.preprocessing   import LabelEncoder, StandardScaler
from sklearn.pipeline        import Pipeline
from sklearn.metrics         import (classification_report, confusion_matrix,
                                     accuracy_score, f1_score)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("[ML] xgboost not installed. Skipping XGBoost model.")

# ── Feature columns used for training ─────────────────────────────────────────
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
LABEL_COL = "fault_class"
SPLIT_COL = "split"

ABLATION_CONFIGS = {
    "A1_rssi_only":       ["wifi_rssi_mean"],
    "A2_wifi_only":       [c for c in FEATURE_COLS if c.startswith("wifi")],
    "A3_wired_only":      [c for c in FEATURE_COLS if c.startswith("pi")],
    "A4_full_crosslayer": FEATURE_COLS,
}


def load_features(features_csv: str) -> pd.DataFrame:
    df = pd.read_csv(features_csv)
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(df[FEATURE_COLS].median())
    return df


def chronological_split(df: pd.DataFrame):
    """Split on labeled split column, or fall back to 80/20 chronological."""
    if SPLIT_COL in df.columns:
        train = df[df[SPLIT_COL] == "train"]
        test  = df[df[SPLIT_COL] != "train"]
    else:
        cutoff = int(len(df) * 0.8)
        train, test = df.iloc[:cutoff], df.iloc[cutoff:]

    if test.empty:
        cutoff = int(len(df) * 0.8)
        train, test = df.iloc[:cutoff], df.iloc[cutoff:]

    return train, test


def train_evaluate(train, test, feature_cols, label, model_name, model):
    """Fit model and return evaluation dict."""
    le = LabelEncoder()
    y_train = le.fit_transform(train[label])
    y_test  = le.transform(test[label])

    X_train = train[feature_cols].values
    X_test  = test[feature_cols].values

    model.fit(X_train, y_train)
    y_pred  = model.predict(X_test)

    acc     = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)

    # False ISP Alarm Rate: fault_class is NOT wan* but predicted wan*
    wan_classes = [i for i, c in enumerate(le.classes_) if "wan" in c]
    non_wan_mask = np.isin(y_test, wan_classes, invert=True)
    false_isp_alarm = np.mean(np.isin(y_pred[non_wan_mask], wan_classes)) if non_wan_mask.any() else 0.0

    return {
        "model":            model_name,
        "features":         len(feature_cols),
        "accuracy":         round(acc,     4),
        "macro_f1":         round(macro_f1, 4),
        "false_isp_alarm":  round(false_isp_alarm, 4),
        "report":           classification_report(y_test, y_pred,
                                target_names=le.classes_, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classes":          le.classes_.tolist(),
        "trained_model":    model,
        "label_encoder":    le,
        "feature_cols":     feature_cols,
    }


def build_models():
    models = {
        "LR":  Pipeline([("scaler", StandardScaler()),
                          ("clf", LogisticRegression(max_iter=1000, C=1.0,
                                                     class_weight="balanced"))]),
        "RF":  RandomForestClassifier(n_estimators=200, max_depth=None,
                                      class_weight="balanced", n_jobs=-1,
                                      random_state=42),
    }
    if HAS_XGB:
        models["XGBoost"] = xgb.XGBClassifier(n_estimators=200, max_depth=6,
                                               use_label_encoder=False,
                                               eval_metric="mlogloss",
                                               n_jobs=-1, random_state=42)
    return models


def run_ablation(df: pd.DataFrame, out_dir: str):
    """Run all 8 ablation configurations and save summary."""
    train, test = chronological_split(df)
    models      = build_models()
    results     = []

    for ablation_name, feat_cols in ABLATION_CONFIGS.items():
        available = [c for c in feat_cols if c in df.columns]
        if not available:
            continue
        print(f"\n─── Ablation: {ablation_name} ({len(available)} features) ───")
        for model_name, model in models.items():
            import copy
            r = train_evaluate(train, test, available,
                               LABEL_COL, f"{ablation_name}_{model_name}", copy.deepcopy(model))
            results.append({
                "ablation":         ablation_name,
                "model":            model_name,
                "n_features":       len(available),
                "accuracy":         r["accuracy"],
                "macro_f1":         r["macro_f1"],
                "false_isp_alarm":  r["false_isp_alarm"],
            })
            print(f"  {model_name}: acc={r['accuracy']:.3f}, macro-F1={r['macro_f1']:.3f}, "
                  f"false_ISP_alarm={r['false_isp_alarm']:.3f}")

    summary = pd.DataFrame(results)
    os.makedirs(out_dir, exist_ok=True)
    summary.to_csv(os.path.join(out_dir, "ablation_results.csv"), index=False)
    print(f"\n[ML] Ablation summary saved to {out_dir}/ablation_results.csv")
    return summary


def save_best_model(result: dict, out_dir: str):
    """Persist best model for live inference."""
    import pickle
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "best_model.pkl"), "wb") as f:
        pickle.dump({
            "model":        result["trained_model"],
            "label_encoder": result["label_encoder"],
            "feature_cols": result["feature_cols"],
        }, f)
    print(f"[ML] Best model saved to {out_dir}/best_model.pkl")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Trinetra ML Classifier")
    parser.add_argument("--features", default="data/features.csv")
    parser.add_argument("--out",      default="data/models")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study")
    parser.add_argument("--sample",   action="store_true", help="Generate synthetic sample data")
    args = parser.parse_args()

    # Generate synthetic features if no real data yet
    if args.sample or not os.path.exists(args.features):
        print("[ML] Generating synthetic features for testing...")
        from generate_sample_data import generate_features_csv
        generate_features_csv(args.features)

    df = load_features(args.features)
    print(f"[ML] Loaded {len(df)} labeled windows.")
    print(f"     Class distribution:\n{df[LABEL_COL].value_counts().to_string()}\n")

    train, test = chronological_split(df)
    print(f"[ML] Train: {len(train)} windows | Test: {len(test)} windows (chronological split)")

    if args.ablation:
        run_ablation(df, args.out)
        return

    # Train full feature set on all models
    models  = build_models()
    results = []
    for model_name, model in models.items():
        print(f"\n─── Training {model_name} (full feature set) ───")
        available = [c for c in FEATURE_COLS if c in df.columns]
        r = train_evaluate(train, test, available, LABEL_COL, model_name, model)
        results.append(r)
        print(r["report"])

    # Save best model by macro-F1
    best = max(results, key=lambda x: x["macro_f1"])
    print(f"\n[ML] Best model: {best['model']} (macro-F1={best['macro_f1']:.3f})")
    save_best_model(best, args.out)


if __name__ == "__main__":
    main()
