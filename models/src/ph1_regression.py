"""
TTC Subway Delay — Phase 1 Stage 2: Regression Pipeline
========================================================
Predicts the *duration* of a delay (minutes) given that a delay has already
been predicted to occur (i.e., operates only on rows where min_delay_capped > 0).

This is the second stage of the two-stage model:
      Stage 1 (ph1_classification.py) → Is a delay likely?
      Stage 2 (this module)                → If so, how long?

Repo path:   models/src/ph1_regression.py
Data path:   data/processing/cleaned_ttc_delay_data.csv
Artifacts:   models/trained/regression/<version>/
Date: Mar. 6th 2026

Usage
-----
      python ph1_regression.py                                        # default data path
      python ph1_regression.py --data path/to/data.csv   # override data path
      python ph1_regression.py --no-tune                        # skip RandomizedSearchCV

Artifacts saved per run
-----------------------
      lgbm_regressor.pkl            — best tuned LightGBM regression model
      one_hot_encoder.pkl          — fitted OneHotEncoder (required at inference)
      feature_names.pkl             — ordered feature names post-encoding
      metrics.json                     — MAE, RMSE, R² for all models
      metadata.json                   — run config, best params, data stats
      feature_importance.json    — feature: importance score (top model only)

Notes
-----
- Training data is filtered to delayed rows only (min_delay_capped > 0).
- The encoder is fitted on ALL training rows (delayed + on-time) to ensure
   every category seen at inference can be handled.
- At inference time you should first filter to predicted-delayed rows, then
   call predict().
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from scipy.stats import randint, uniform
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.preprocessing import OneHotEncoder


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RANDOM_SEED: int = 42
TARGET_COL: str = "min_delay_capped"
DATE_COL: str = "Date"
CATEGORICAL_COLS: List[str] = ["Line", "Station", "Code"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH: Path = _REPO_ROOT / "data" / \
    "processing" / "cleaned_ttc_delay_data.csv"
ARTIFACT_ROOT: Path = _REPO_ROOT / "models" / "trained" / "regression"

N_CV_SPLITS: int = 5
N_SEARCH_ITER: int = 50
TRAIN_RATIO: float = 0.8

LGBM_PARAM_DIST = {
    "n_estimators": randint(50, 500),
    "learning_rate": uniform(0.01, 0.2),
    "num_leaves": randint(20, 100),
    "max_depth": randint(3, 15),
    "min_child_samples": randint(20, 100),
    "subsample": uniform(0.6, 0.4),
    "colsample_bytree": uniform(0.6, 0.4),
    "reg_alpha": uniform(0, 0.5),
    "reg_lambda": uniform(0, 0.5),
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
# Helpers (shared with classification module; duplicated to keep modules independent)
# ---------------------------------------------------------------------------

def sanitize_feature_names(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to be LightGBM-compatible (no special chars) and unique."""
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
# Data loading & validation
# ---------------------------------------------------------------------------

def load_and_validate(data_path: Path) -> pd.DataFrame:
    log.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path, parse_dates=[DATE_COL])

    required = set(CATEGORICAL_COLS + [TARGET_COL])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    if df[TARGET_COL].isnull().any():
        raise ValueError(f"Target column '{TARGET_COL}' contains null values.")

    log.info(f"Loaded {len(df):,} rows | {df.shape[1]} columns")
    n_delayed = int((df[TARGET_COL] > 0).sum())
    log.info(
        f"Delayed rows: {n_delayed:,} ({n_delayed / len(df):.1%} of total)")
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
    Encode categorical columns and return the full feature matrix.

    IMPORTANT: Always fit the encoder on the FULL training split (not just
    delayed rows) so that all categories are learned. Then filter rows for
    regression after encoding.

    Parameters
    ----------
    df               : Raw DataFrame (may include target column; it will be dropped).
    ohe             : Pre-fitted encoder — pass when transforming test data.
    fit_encoder : Fit a new encoder when True; transform-only when False.

    Returns
    -------
    X_encoded       : Feature DataFrame with sanitized column names.
    ohe                : The encoder (fitted or provided).
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

    return X_encoded, ohe, feature_names


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def compute_metrics(
    model, X: pd.DataFrame, y: pd.Series
) -> Dict[str, float | None]:
    """Return MAE, RMSE, and R² for a regression model."""
    preds = model.predict(X)
    return {
        "mae": round(float(mean_absolute_error(y, preds)), 4),
        "rmse": round(float(root_mean_squared_error(y, preds)), 4),
        "r2": round(float(r2_score(y, preds)), 4),
    }


def compute_baseline_metrics(
    y_train: pd.Series, y_test: pd.Series
) -> Dict[str, Dict]:
    """Evaluate mean and median baselines against the test set."""
    mean_pred = float(y_train.mean())
    median_pred = float(y_train.median())

    def _metrics(constant: float) -> Dict:
        preds = np.full(len(y_test), constant)
        return {
            "constant_value_minutes": round(constant, 2),
            "mae": round(float(mean_absolute_error(y_test, preds)), 4),
            "rmse": round(float(root_mean_squared_error(y_test, preds)), 4),
            "r2": round(float(r2_score(y_test, preds)), 4),
        }

    return {
        "baseline_mean": _metrics(mean_pred),
        "baseline_median": _metrics(median_pred),
    }


# ---------------------------------------------------------------------------
# Training pipeline
# ---------------------------------------------------------------------------

def run_regression(data_path: Path, tune: bool = True) -> Path:
    """
    Full Stage 2 regression training pipeline.
    Returns the path to the versioned artifact directory.
    """
    # ── 1. Load & sort ────────────────────────────────────────────────────
    df = load_and_validate(data_path)
    df = df.sort_values(DATE_COL).reset_index(drop=True)

    # ── 2. Time-based split on the FULL dataset ───────────────────────────
    split_idx = int(len(df) * TRAIN_RATIO)
    train_full = df.iloc[:split_idx]
    test_full = df.iloc[split_idx:]

    # ── 3. Fit encoder on full training split (all rows, not just delayed) ─
    #      This ensures no categories are missed when encoding at inference time.
    X_train_full, ohe, feature_names = build_feature_matrix(
        train_full, fit_encoder=True)
    X_test_full, _, _ = build_feature_matrix(
        test_full, ohe=ohe, fit_encoder=False)

    # ── 4. Filter to delayed rows only for regression ─────────────────────
    train_delayed_mask = train_full[TARGET_COL] > 0
    test_delayed_mask = test_full[TARGET_COL] > 0

    X_train = X_train_full.loc[train_delayed_mask]
    y_train = train_full.loc[train_delayed_mask,
                             TARGET_COL].reset_index(drop=True)
    X_train = X_train.reset_index(drop=True)

    X_test = X_test_full.loc[test_delayed_mask]
    y_test = test_full.loc[test_delayed_mask,
                           TARGET_COL].reset_index(drop=True)
    X_test = X_test.reset_index(drop=True)

    log.info(
        f"Regression subsets — train: {X_train.shape}, test: {X_test.shape}"
    )
    log.info(
        f"Delay duration stats (train) — "
        f"mean={y_train.mean():.1f} min, median={y_train.median():.0f} min, "
        f"max={y_train.max():.0f} min"
    )

    # ── 5. Baselines ──────────────────────────────────────────────────────
    all_metrics: Dict[str, Dict] = compute_baseline_metrics(y_train, y_test)
    log.info(
        f"Baseline MAE — mean: {all_metrics['baseline_mean']['mae']} min, "
        f"median: {all_metrics['baseline_median']['mae']} min"
    )

    # ── 6. Initial (untuned) LightGBM ────────────────────────────────────
    lgbm_init = LGBMRegressor(random_state=RANDOM_SEED, n_jobs=-1, verbose=-1)
    lgbm_init.fit(X_train, y_train)
    all_metrics["lightgbm_untuned"] = compute_metrics(
        lgbm_init, X_test, y_test)
    log.info(
        f"Untuned LightGBM — MAE={all_metrics['lightgbm_untuned']['mae']} | "
        f"RMSE={all_metrics['lightgbm_untuned']['rmse']}"
    )

    # ── 7. Hyperparameter tuning ──────────────────────────────────────────
    lgbm_base = LGBMRegressor(random_state=RANDOM_SEED, n_jobs=-1, verbose=-1)

    if tune:
        log.info(
            f"Starting RandomizedSearchCV ({N_SEARCH_ITER} iterations, "
            f"{N_CV_SPLITS} CV folds, scoring=neg_mean_absolute_error)"
        )
        tscv = TimeSeriesSplit(n_splits=N_CV_SPLITS)
        search = RandomizedSearchCV(
            estimator=lgbm_base,
            param_distributions=LGBM_PARAM_DIST,
            n_iter=N_SEARCH_ITER,
            scoring="neg_mean_absolute_error",
            cv=tscv,
            random_state=RANDOM_SEED,
            n_jobs=-1,
            verbose=0,
        )
        search.fit(X_train, y_train)
        best_model = search.best_estimator_
        best_params = search.best_params_
        best_cv_mae = round(float(-search.best_score_), 4)
        log.info(f"Best CV MAE: {best_cv_mae} min | Params: {best_params}")
    else:
        log.info("Tuning skipped — using default LightGBM params")
        lgbm_base.fit(X_train, y_train)
        best_model = lgbm_base
        best_params = lgbm_base.get_params()
        best_cv_mae = None

    all_metrics["lightgbm_tuned"] = compute_metrics(best_model, X_test, y_test)
    log.info(
        f"Tuned LightGBM — MAE={all_metrics['lightgbm_tuned']['mae']} | "
        f"RMSE={all_metrics['lightgbm_tuned']['rmse']} | "
        f"R²={all_metrics['lightgbm_tuned']['r2']}"
    )

    # ── 8. Feature importance ─────────────────────────────────────────────
    feature_importance = dict(
        sorted(
            zip(feature_names, best_model.feature_importances_.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
    )

    # ── 9. Save artifacts ─────────────────────────────────────────────────
    version, artifact_dir = make_version_dir()

    joblib.dump(best_model, artifact_dir / "lgbm_regressor.pkl")
    joblib.dump(ohe, artifact_dir / "one_hot_encoder.pkl")
    joblib.dump(feature_names, artifact_dir / "feature_names.pkl")

    save_json(all_metrics, artifact_dir / "metrics.json")
    save_json(feature_importance, artifact_dir / "feature_importance.json")
    save_json(
        {
            "version": version,
            "trained_at": datetime.datetime.utcnow().isoformat(),
            "data_path": str(data_path),
            "random_seed": RANDOM_SEED,
            "train_rows_total": int(len(train_full)),
            "train_rows_delayed": int(len(X_train)),
            "test_rows_total": int(len(test_full)),
            "test_rows_delayed": int(len(X_test)),
            "n_features": len(feature_names),
            "target_column": TARGET_COL,
            "target_scope": "delayed rows only (min_delay_capped > 0)",
            "categorical_columns": CATEGORICAL_COLS,
            "train_delay_mean_minutes": round(float(y_train.mean()), 2),
            "train_delay_median_minutes": round(float(y_train.median()), 2),
            "best_cv_mae_minutes": best_cv_mae,
            "best_params": best_params,
        },
        artifact_dir / "metadata.json",
    )

    log.info(f"Artifacts saved → {artifact_dir}")
    return artifact_dir


# ---------------------------------------------------------------------------
# Inference helper (for chatbot integration)
# ---------------------------------------------------------------------------

def load_regressor(
    artifact_dir: Path,
) -> Tuple[LGBMRegressor, OneHotEncoder, List[str]]:
    """
    Load a saved regressor and its preprocessing objects.

    Example
    -------
          model, ohe, feature_names = load_regressor(Path("models/trained/regression/v20260301_120000"))
          X, _, _ = build_feature_matrix(predicted_delayed_df, ohe=ohe, fit_encoder=False)
          durations = model.predict(X)    # predicted minutes
    """
    model = joblib.load(artifact_dir / "lgbm_regressor.pkl")
    ohe = joblib.load(artifact_dir / "one_hot_encoder.pkl")
    feature_names = joblib.load(artifact_dir / "feature_names.pkl")
    return model, ohe, feature_names


def predict_duration(
    new_df: pd.DataFrame,
    artifact_dir: Path,
) -> pd.Series:
    """
    Predict delay duration (minutes) for new data.

    Parameters
    ----------
    new_df          : DataFrame of rows already predicted as "delayed" by Stage 1.
                           Must contain the same raw feature columns as training data.
    artifact_dir : Path to a versioned artifact directory from run_regression().

    Returns
    -------
    pd.Series of predicted delay durations (float, minutes), indexed like new_df.
    """
    model, ohe, _ = load_regressor(artifact_dir)
    X, _, _ = build_feature_matrix(new_df, ohe=ohe, fit_encoder=False)
    preds = model.predict(X)
    return pd.Series(preds, index=new_df.index, name="predicted_delay_minutes")


# ---------------------------------------------------------------------------
# Two-stage combined prediction (convenience function for chatbot)
# ---------------------------------------------------------------------------

def two_stage_predict(
    new_df: pd.DataFrame,
    classifier_artifact_dir: Path,
    regressor_artifact_dir: Path,
    delay_threshold: float = 0.5,
) -> pd.DataFrame:
    """
    Run the full two-stage pipeline on new data.

    Stage 1: Classify delay vs. on-time.
    Stage 2: For rows predicted as delayed, estimate duration.

    Parameters
    ----------
    new_df                              : Raw feature DataFrame (no target column).
    classifier_artifact_dir    : Versioned artifact directory from ph1_classification.py.
    regressor_artifact_dir      : Versioned artifact directory from ph1_regression.py.
    delay_threshold                : Probability threshold for classifying as delayed.

    Returns
    -------
    DataFrame with columns:
          predicted_label               — 1 = delayed, 0 = on-time
          delay_probability            — Stage 1 probability score
          predicted_delay_minutes   — Stage 2 duration estimate (NaN if predicted on-time)
    """
    # Lazy import to avoid circular dependency if used as a library
    from ph1_classification import (
        build_feature_matrix as clf_build,
        load_classifier,
    )

    # ── Stage 1 ──────────────────────────────────────────────────────────
    clf_model, clf_ohe, _ = load_classifier(classifier_artifact_dir)
    X_clf, _, _ = clf_build(new_df, ohe=clf_ohe, fit_encoder=False)
    probs = clf_model.predict_proba(X_clf)[:, 1]
    labels = (probs >= delay_threshold).astype(int)

    result = pd.DataFrame(
        {
            "predicted_label": labels,
            "delay_probability": probs,
            "predicted_delay_minutes": np.nan,
        },
        index=new_df.index,
    )

    # ── Stage 2 (delayed rows only) ───────────────────────────────────────
    delayed_mask = labels == 1
    if delayed_mask.any():
        delayed_rows = new_df.loc[delayed_mask]
        reg_model, reg_ohe, _ = load_regressor(regressor_artifact_dir)
        X_reg, _, _ = build_feature_matrix(
            delayed_rows, ohe=reg_ohe, fit_encoder=False)
        durations = reg_model.predict(X_reg)
        result.loc[delayed_mask, "predicted_delay_minutes"] = durations

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TTC Phase 1 Stage 2 — Delay Duration Regression")
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
        help="Skip RandomizedSearchCV (faster, uses default LightGBM params)",
    )
    args = parser.parse_args()

    artifact_dir = run_regression(data_path=args.data, tune=not args.no_tune)
    log.info(f"Pipeline complete. Artifacts at: {artifact_dir}")
