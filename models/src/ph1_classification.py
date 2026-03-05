"""
TTC Subway Delay — Phase 1: Binary Classification Pipeline
==========================================================
Predicts whether a subway event will result in a delay (binary: delayed vs. on-time).

Repo path:   models/src/ph1_classification.py
Data path:   data/processing/cleaned_ttc_delay_data.csv
Artifacts:   models/trained/classification/<version>/

Usage
-----
      python ph1_classification.py                                        # default data path
      python ph1_classification.py --data path/to/data.csv   # override data path
      python ph1_classification.py --no-tune                        # skip RandomizedSearchCV

Artifacts saved per run
-----------------------
      lgbm_classifier.pkl          — best tuned LightGBM classifier
      one_hot_encoder.pkl          — fitted OneHotEncoder (required at inference)
      feature_names.pkl             — ordered feature names post-encoding
      metrics.json                     — full metrics for every model (accuracy, precision,
                                                recall, f1, roc_auc, auc_pr, confusion_matrix)
      metrics_comparison.json    — structured side-by-side comparison table
      metadata.json                   — run config, best params, data stats, CV score
      feature_importance.json    — {feature: importance} sorted descending (best model)

Pipeline stages
---------------
      1.   Load and validate
      2.   Chronological sort + 80/20 time-based split
      3.   Feature encoding   (OHE fit on train only, transform test)
      4.   Binary target conversion   (min_delay_capped > 0)
      5.   Baseline: Majority Class   (always predicts on-time)
      6.   Baseline: Historical Rate   (stratified by class frequency)
      7.   Logistic Regression
      8.   Random Forest Classifier
      9.   LightGBM (untuned)
      10. LightGBM (tuned via RandomizedSearchCV + TimeSeriesSplit)
      11. Full metrics comparison table
      12. Feature importance extraction
      13. Artifact persistence
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from scipy.stats import randint, uniform
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
      accuracy_score,
      auc,
      confusion_matrix,
      f1_score,
      precision_recall_curve,
      precision_score,
      recall_score,
      roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.preprocessing import OneHotEncoder


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RANDOM_SEED: int = 42
TARGET_COL: str = "min_delay_capped"
DATE_COL: str = "Date"
CATEGORICAL_COLS: List[str] = ["Line", "Station", "Code"]

_REPO_ROOT = Path(__file__).resolve().parents[2]    # models/src/ -> repo root
DEFAULT_DATA_PATH: Path = (
      _REPO_ROOT / "data" / "processing" / "cleaned_ttc_delay_data.csv"
)
ARTIFACT_ROOT: Path = _REPO_ROOT / "models" / "trained" / "classification"

N_CV_SPLITS: int = 5
TRAIN_RATIO: float = 0.8
N_SEARCH_ITER: int = 50    # matches the notebook

LGBM_PARAM_DIST: Dict[str, Any] = {
      "n_estimators":         randint(50, 500),
      "learning_rate":       uniform(0.01, 0.2),
      "num_leaves":            randint(20, 100),
      "max_depth":             randint(3, 15),
      "min_child_samples": randint(20, 100),
      "subsample":             uniform(0.6, 0.4),
      "colsample_bytree":   uniform(0.6, 0.4),
      "reg_alpha":             uniform(0, 0.5),
      "reg_lambda":            uniform(0, 0.5),
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s | %(levelname)s | %(message)s",
      handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def sanitize_feature_names(df: pd.DataFrame) -> pd.DataFrame:
      """
      Rename columns to be LightGBM-safe (no special chars, unique names).
      Replicates sanitize_and_uniquify_feature_names_lgbm() from the notebook.
      """
      original = df.columns.tolist()
      final: List[str] = []
      seen: set = set()
      base_counts: dict = defaultdict(int)

      for col in original:
            cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", col)
            cleaned = re.sub(r"^_+|_+$", "", cleaned)
            cleaned = re.sub(r"_+", "_", cleaned) or "feature"

            name = cleaned
            suffix = base_counts[cleaned]
            while name in seen:
                  suffix += 1
                  name = f"{cleaned}_{suffix}"

            seen.add(name)
            base_counts[cleaned] = suffix
            final.append(name)

      return df.rename(columns=dict(zip(original, final)))


def make_version_dir() -> Tuple[str, Path]:
      version = datetime.datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
      path = ARTIFACT_ROOT / version
      path.mkdir(parents=True, exist_ok=True)
      return version, path


def save_json(obj: dict, path: Path) -> None:
      with open(path, "w") as fh:
            json.dump(obj, fh, indent=4, default=str)


# ---------------------------------------------------------------------------
# Data loading and validation
# ---------------------------------------------------------------------------

def load_and_validate(data_path: Path) -> pd.DataFrame:
      log.info(f"Loading data from {data_path}")
      df = pd.read_csv(data_path, parse_dates=[DATE_COL])

      required = set(CATEGORICAL_COLS + [TARGET_COL])
      missing = required - set(df.columns)
      if missing:
            raise ValueError(f"Dataset missing required columns: {missing}")
      if df[TARGET_COL].isnull().any():
            raise ValueError(f"Target column '{TARGET_COL}' contains null values.")

      log.info(f"Loaded {len(df):,} rows | {df.shape[1]} columns")
      log.info(f"Zero-delay ratio: {(df[TARGET_COL] == 0).mean():.1%}")
      return df


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def build_feature_matrix(
      df: pd.DataFrame,
      ohe: OneHotEncoder | None = None,
      fit_encoder: bool = True,
) -> Tuple[pd.DataFrame, OneHotEncoder, List[str]]:
      """
      One-hot encode categorical columns and return the sanitized feature matrix.

      Always fit on training data only. Pass the fitted encoder when
      transforming test/inference data to prevent leakage.

      Parameters
      ----------
      df               : Raw DataFrame (target and date columns are dropped if present).
      ohe             : Pre-fitted encoder — required when fit_encoder=False.
      fit_encoder : Fit a new encoder when True; transform-only when False.

      Returns
      -------
      X_encoded       : Feature DataFrame with LightGBM-safe column names.
      ohe                : The fitted encoder.
      feature_names : Ordered list of column names in X_encoded.
      """
      drop_cols = [c for c in [DATE_COL, TARGET_COL] if c in df.columns]
      X_raw = df.drop(columns=drop_cols)
      numeric_cols = [c for c in X_raw.columns if c not in CATEGORICAL_COLS]

      if fit_encoder:
            ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
            ohe.fit(X_raw[CATEGORICAL_COLS])

      X_cat = ohe.transform(X_raw[CATEGORICAL_COLS])
      X_cat_df = pd.DataFrame(
            X_cat,
            columns=ohe.get_feature_names_out(CATEGORICAL_COLS),
            index=X_raw.index,
      )

      X_encoded = pd.concat([X_raw[numeric_cols], X_cat_df], axis=1)
      X_encoded = sanitize_feature_names(X_encoded)
      feature_names = X_encoded.columns.tolist()

      log.info(f"Feature matrix shape: {X_encoded.shape}")
      return X_encoded, ohe, feature_names


def make_binary_target(y_continuous: pd.Series) -> pd.Series:
      """1 = delayed (min_delay_capped > 0), 0 = on-time."""
      return (y_continuous > 0).astype(int)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def compute_metrics(
      model,
      X: pd.DataFrame,
      y: pd.Series,
      model_name: str = "",
) -> Dict[str, Any]:
      """
      Compute the full classification metrics from the notebook:
            accuracy, precision, recall, f1, roc_auc, auc_pr, confusion_matrix.

      AUC-PR is included because the dataset is imbalanced (64/36 split) and
      AUC-PR gives a more informative picture of minority-class performance
      than AUC-ROC alone — the notebook calls this out explicitly in section 7.1.

      Confusion matrix is saved as [[TN, FP], [FN, TP]] for downstream use
      (e.g., model-evaluation.md, chatbot response confidence logic).

      DummyClassifiers with most_frequent strategy produce trivial probabilities
      that break roc_auc_score; those fields are left as None.
      """
      preds = model.predict(X)
      cm = confusion_matrix(y, preds).tolist()

      metrics: Dict[str, Any] = {
            "accuracy":             round(float(accuracy_score(y, preds)), 4),
            "precision":            round(float(precision_score(y, preds, zero_division=0)), 4),
            "recall":                round(float(recall_score(y, preds, zero_division=0)), 4),
            "f1_score":             round(float(f1_score(y, preds, zero_division=0)), 4),
            "confusion_matrix": cm,
            "roc_auc":               None,
            "auc_pr":                None,
      }

      try:
            probs = model.predict_proba(X)[:, 1]
            metrics["roc_auc"] = round(float(roc_auc_score(y, probs)), 4)
            precision_curve, recall_curve, _ = precision_recall_curve(y, probs)
            metrics["auc_pr"] = round(float(auc(recall_curve, precision_curve)), 4)
      except Exception:
            pass

      if model_name:
            log.info(
                  f"   {model_name:<30} | "
                  f"Acc={metrics['accuracy']} | "
                  f"Prec={metrics['precision']} | "
                  f"Recall={metrics['recall']} | "
                  f"F1={metrics['f1_score']} | "
                  f"AUC-ROC={metrics['roc_auc']} | "
                  f"AUC-PR={metrics['auc_pr']}"
            )

      return metrics


def build_comparison_table(all_metrics: Dict[str, Dict]) -> List[Dict]:
      """
      Build the side-by-side model comparison that mirrors the notebook's
      summary table in section 6.1. Sorted by F1 descending.
      Confusion matrix is excluded here (it lives in metrics.json per model).
      """
      rows = []
      for model_name, m in all_metrics.items():
            rows.append({
                  "model":       model_name,
                  "accuracy":   m["accuracy"],
                  "precision": m["precision"],
                  "recall":      m["recall"],
                  "f1_score":   m["f1_score"],
                  "roc_auc":    m["roc_auc"],
                  "auc_pr":      m["auc_pr"],
            })
      return sorted(rows, key=lambda r: (r["f1_score"] or 0), reverse=True)


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------

def run_classification(data_path: Path, tune: bool = True) -> Path:
      """
      Full binary classification training pipeline.
      Returns the path to the versioned artifact directory.
      """

      # ── 1. Load and validate ──────────────────────────────────────────────
      df = load_and_validate(data_path)
      df = df.sort_values(DATE_COL).reset_index(drop=True)

      # ── 2. Time-based train / test split ──────────────────────────────────
      split_idx = int(len(df) * TRAIN_RATIO)
      train_df = df.iloc[:split_idx]
      test_df   = df.iloc[split_idx:]
      log.info(
            f"Split index: {split_idx} "
            f"(train: {len(train_df):,} rows | test: {len(test_df):,} rows)"
      )

      # ── 3. Feature encoding ───────────────────────────────────────────────
      X_train, ohe, feature_names = build_feature_matrix(train_df, fit_encoder=True)
      X_test,   _,    _                   = build_feature_matrix(test_df, ohe=ohe, fit_encoder=False)

      # ── 4. Binary target ──────────────────────────────────────────────────
      y_train = make_binary_target(train_df[TARGET_COL])
      y_test   = make_binary_target(test_df[TARGET_COL])

      train_delay_rate = round(float(y_train.mean()), 4)
      test_delay_rate   = round(float(y_test.mean()), 4)
      log.info(
            f"Binary class distribution (train) — "
            f"on-time: {1 - train_delay_rate:.1%} | delayed: {train_delay_rate:.1%}"
      )

      all_metrics: Dict[str, Dict] = {}

      # ── 5. Baseline: Majority Class ───────────────────────────────────────
      # Always predicts on-time (the majority class). Sets a naive accuracy
      # floor — any real model must beat this on F1 and Recall.
      log.info("--- Baselines ---")
      majority_model = DummyClassifier(strategy="most_frequent", random_state=RANDOM_SEED)
      majority_model.fit(X_train, y_train)
      all_metrics["baseline_majority_class"] = compute_metrics(
            majority_model, X_test, y_test, "baseline_majority_class"
      )

      # ── 6. Baseline: Historical Delay Rate ────────────────────────────────
      # Predicts delayed/on-time proportionally to their training frequency.
      # Provides a non-zero F1 floor and a more meaningful lower bound than
      # the majority-class baseline for the delayed minority class.
      stratified_model = DummyClassifier(strategy="stratified", random_state=RANDOM_SEED)
      stratified_model.fit(X_train, y_train)
      all_metrics["baseline_historical_rate"] = compute_metrics(
            stratified_model, X_test, y_test, "baseline_historical_rate"
      )

      # ── 7. Logistic Regression ────────────────────────────────────────────
      # solver=liblinear, C=0.1 matches the notebook (section 5.1).
      log.info("--- Model Training ---")
      log_reg = LogisticRegression(
            solver="liblinear",
            C=0.1,
            random_state=RANDOM_SEED,
            max_iter=1000,
      )
      log_reg.fit(X_train, y_train)
      all_metrics["logistic_regression"] = compute_metrics(
            log_reg, X_test, y_test, "logistic_regression"
      )

      # ── 8. Random Forest Classifier ───────────────────────────────────────
      # n_estimators=100, max_depth=10, class_weight='balanced' matches
      # section 5.2 of the notebook.
      rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight="balanced",
            random_state=RANDOM_SEED,
            n_jobs=-1,
      )
      rf_model.fit(X_train, y_train)
      all_metrics["random_forest"] = compute_metrics(
            rf_model, X_test, y_test, "random_forest"
      )

      # ── 9. LightGBM untuned ───────────────────────────────────────────────
      # n_estimators=100, no class_weight — baseline LightGBM performance
      # before hyperparameter tuning (section 5.3 of the notebook).
      lgbm_untuned = LGBMClassifier(
            n_estimators=100,
            random_state=RANDOM_SEED,
            n_jobs=-1,
            verbose=-1,
      )
      lgbm_untuned.fit(X_train, y_train)
      all_metrics["lightgbm_untuned"] = compute_metrics(
            lgbm_untuned, X_test, y_test, "lightgbm_untuned"
      )

      # ── 10. LightGBM hyperparameter tuning ───────────────────────────────
      # class_weight='balanced' + TimeSeriesSplit(5) + scoring='f1'
      # + RandomizedSearchCV(50 iter) — replicates section 6.1 exactly.
      lgbm_base = LGBMClassifier(
            random_state=RANDOM_SEED,
            class_weight="balanced",
            n_jobs=-1,
            verbose=-1,
      )

      best_cv_score: float | None = None
      best_params: dict = {}

      if tune:
            log.info(
                  f"--- Hyperparameter Tuning (RandomizedSearchCV) ---\n"
                  f"      {N_SEARCH_ITER} iterations | {N_CV_SPLITS} TimeSeriesSplit folds | scoring=f1"
            )
            tscv = TimeSeriesSplit(n_splits=N_CV_SPLITS)
            search = RandomizedSearchCV(
                  estimator=lgbm_base,
                  param_distributions=LGBM_PARAM_DIST,
                  n_iter=N_SEARCH_ITER,
                  scoring="f1",
                  cv=tscv,
                  random_state=RANDOM_SEED,
                  n_jobs=-1,
                  verbose=0,
            )
            search.fit(X_train, y_train)
            best_model = search.best_estimator_
            best_params = {k: str(v) for k, v in search.best_params_.items()}
            best_cv_score = round(float(search.best_score_), 4)
            log.info(f"Best CV F1: {best_cv_score}")
            log.info(f"Best params: {best_params}")
      else:
            log.info("Tuning skipped — fitting LightGBM with default params")
            lgbm_base.fit(X_train, y_train)
            best_model = lgbm_base
            best_params = {k: str(v) for k, v in lgbm_base.get_params().items()}

      all_metrics["lightgbm_tuned"] = compute_metrics(
            best_model, X_test, y_test, "lightgbm_tuned"
      )

      # ── 11. Metrics comparison table ─────────────────────────────────────
      log.info("--- Model Comparison (sorted by F1) ---")
      comparison_table = build_comparison_table(all_metrics)
      for row in comparison_table:
            log.info(
                  f"   {row['model']:<30} | F1={row['f1_score']} | "
                  f"Recall={row['recall']} | AUC-ROC={row['roc_auc']} | AUC-PR={row['auc_pr']}"
            )

      # ── 12. Feature importance ────────────────────────────────────────────
      feature_importance = dict(
            sorted(
                  zip(feature_names, best_model.feature_importances_.tolist()),
                  key=lambda x: x[1],
                  reverse=True,
            )
      )
      log.info("Top 10 features (tuned LightGBM):")
      for feat, score in list(feature_importance.items())[:10]:
            log.info(f"   {feat}: {score}")

      # ── 13. Save artifacts ────────────────────────────────────────────────
      version, artifact_dir = make_version_dir()

      joblib.dump(best_model,       artifact_dir / "lgbm_classifier.pkl")
      joblib.dump(ohe,                  artifact_dir / "one_hot_encoder.pkl")
      joblib.dump(feature_names,   artifact_dir / "feature_names.pkl")

      save_json(all_metrics,            artifact_dir / "metrics.json")
      save_json(comparison_table,    artifact_dir / "metrics_comparison.json")
      save_json(feature_importance, artifact_dir / "feature_importance.json")

      tuned_m = all_metrics["lightgbm_tuned"]
      save_json(
            {
                  "version":                   version,
                  "trained_at":               datetime.datetime.utcnow().isoformat(),
                  "data_path":                str(data_path),
                  "random_seed":             RANDOM_SEED,
                  "train_rows":               int(len(train_df)),
                  "test_rows":                int(len(test_df)),
                  "n_features":               len(feature_names),
                  "target_column":          TARGET_COL,
                  "target_conversion":    "binary: 1 if min_delay_capped > 0 else 0",
                  "categorical_columns": CATEGORICAL_COLS,
                  "train_delay_rate":      train_delay_rate,
                  "test_delay_rate":       test_delay_rate,
                  "best_model":               "lightgbm_tuned",
                  "best_cv_f1":               best_cv_score,
                  "best_test_f1":            tuned_m["f1_score"],
                  "best_test_recall":      tuned_m["recall"],
                  "best_test_precision": tuned_m["precision"],
                  "best_test_roc_auc":    tuned_m["roc_auc"],
                  "best_test_auc_pr":      tuned_m["auc_pr"],
                  "best_params":             best_params,
            },
            artifact_dir / "metadata.json",
      )

      log.info(f"All artifacts saved -> {artifact_dir}")
      return artifact_dir


# ---------------------------------------------------------------------------
# Inference helpers (for chatbot integration)
# ---------------------------------------------------------------------------

def load_classifier(
      artifact_dir: Path,
) -> Tuple[LGBMClassifier, OneHotEncoder, List[str]]:
      """
      Load a saved classifier and its preprocessing objects.

      Example
      -------
            model, ohe, feature_names = load_classifier(
                  Path("models/trained/classification/v20260301_120000")
            )
            X, _, _ = build_feature_matrix(new_df, ohe=ohe, fit_encoder=False)
            labels = model.predict(X)
            probs   = model.predict_proba(X)[:, 1]
      """
      model             = joblib.load(artifact_dir / "lgbm_classifier.pkl")
      ohe                = joblib.load(artifact_dir / "one_hot_encoder.pkl")
      feature_names = joblib.load(artifact_dir / "feature_names.pkl")
      return model, ohe, feature_names


def predict(
      new_df: pd.DataFrame,
      artifact_dir: Path,
      threshold: float = 0.5,
) -> pd.DataFrame:
      """
      Run inference on new data.

      Parameters
      ----------
      new_df          : Raw feature DataFrame (same columns as training, no target).
      artifact_dir : Versioned artifact directory from run_classification().
      threshold      : Probability cutoff for the delayed class. Lowering this
                             increases recall at the cost of more false alarms —
                             appropriate for commuter-facing delay alerts.

      Returns
      -------
      DataFrame with columns:
            predicted_label      — 1 = delayed, 0 = on-time
            delay_probability   — raw model probability for class 1
      """
      model, ohe, _ = load_classifier(artifact_dir)
      X, _, _          = build_feature_matrix(new_df, ohe=ohe, fit_encoder=False)
      probs             = model.predict_proba(X)[:, 1]
      labels            = (probs >= threshold).astype(int)

      return pd.DataFrame(
            {"predicted_label": labels, "delay_probability": probs},
            index=new_df.index,
      )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
      parser = argparse.ArgumentParser(
            description="TTC Phase 1 — Delay Binary Classification"
      )
      parser.add_argument(
            "--data",
            type=Path,
            default=DEFAULT_DATA_PATH,
            help="Path to cleaned_ttc_delay_data.csv",
      )
      parser.add_argument(
            "--no-tune",
            action="store_true",
            default=False,
            help="Skip RandomizedSearchCV (faster; uses default LightGBM params)",
      )
      args = parser.parse_args()

      artifact_dir = run_classification(data_path=args.data, tune=not args.no_tune)
      log.info(f"Pipeline complete. Artifacts at: {artifact_dir}")
