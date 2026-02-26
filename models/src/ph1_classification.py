"""
TTC Subway Delay Classification Pipeline
Production-Ready Training Script

Stage 1:
- Data preparation
- Feature encoding
- Time-based split
- Binary target creation
- Model training (Logistic, Random Forest, LightGBM)
- Hyperparameter tuning (LightGBM)
- Evaluation
- Artifact persistence

Author: ...
Date: February 2026
"""

# =========================
# Imports
# =========================

import os
import re
import warnings
import joblib
import numpy as np
import pandas as pd

from collections import defaultdict
from scipy.stats import uniform, randint

from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_curve,
    roc_auc_score,
    precision_recall_curve,
    auc
)

from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")


# =========================
# Utility Functions
# =========================

def ensure_directory(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


def load_data(filepath: str) -> pd.DataFrame:
    return pd.read_csv(filepath, parse_dates=["Date"])


def prepare_features_and_target(df: pd.DataFrame, target_col: str):
    y = df[target_col]
    X = df.drop(columns=["Date", target_col])

    cat_cols = ["Line", "Station", "Code"]
    num_cols = [c for c in X.columns if c not in cat_cols]

    return X, y, cat_cols, num_cols


def encode_categorical_features(X: pd.DataFrame, cat_cols: list, output_dir: str):
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X_cat = ohe.fit_transform(X[cat_cols])

    X_cat_df = pd.DataFrame(
        X_cat,
        columns=ohe.get_feature_names_out(cat_cols),
        index=X.index
    )

    X_encoded = pd.concat([X.drop(columns=cat_cols), X_cat_df], axis=1)

    joblib.dump(ohe, os.path.join(output_dir, "one_hot_encoder.pkl"))
    return X_encoded


def sanitize_feature_names_lgbm(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    original_cols = df_copy.columns.tolist()

    final_cols = []
    seen = set()
    base_counts = defaultdict(int)

    for col in original_cols:
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", col)
        cleaned = re.sub(r"^_+|_+$", "", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned)

        if not cleaned:
            cleaned = "feature"

        name = cleaned
        suffix = base_counts[cleaned]

        while name in seen:
            suffix += 1
            name = f"{cleaned}_{suffix}"

        seen.add(name)
        base_counts[cleaned] = suffix
        final_cols.append(name)

    df_copy.columns = final_cols
    return df_copy


def time_series_split(X, y, split_ratio=0.8):
    split_index = int(len(X) * split_ratio)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]
    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    return X_train, X_test, y_train, y_test


def create_binary_target(y: pd.Series) -> pd.Series:
    return (y > 0).astype(int)


# =========================
# Model Training
# =========================

def train_models(X_train, y_train, X_test, y_test, output_dir):

    results = {}

    # Logistic Regression
    log_model = LogisticRegression(
        solver="liblinear",
        C=0.1,
        random_state=42
    )
    log_model.fit(X_train, y_train)
    y_pred_log = log_model.predict(X_test)

    joblib.dump(log_model, os.path.join(output_dir, "logistic_model.pkl"))

    results["logistic_regression"] = evaluate_basic(
        y_test, y_pred_log
    )

    # Random Forest
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        class_weight="balanced",
        random_state=42
    )
    rf_model.fit(X_train, y_train)
    y_pred_rf = rf_model.predict(X_test)

    joblib.dump(rf_model, os.path.join(output_dir, "random_forest_model.pkl"))

    results["random_forest"] = evaluate_basic(
        y_test, y_pred_rf
    )

    # LightGBM (untuned)
    X_train_lgbm = sanitize_feature_names_lgbm(X_train)
    X_test_lgbm = sanitize_feature_names_lgbm(X_test)

    lgbm_model = LGBMClassifier(
        n_estimators=100,
        random_state=42
    )

    lgbm_model.fit(X_train_lgbm, y_train)
    y_pred_lgbm = lgbm_model.predict(X_test_lgbm)

    joblib.dump(lgbm_model, os.path.join(output_dir, "lgbm_untuned_model.pkl"))

    results["lightgbm_untuned"] = evaluate_basic(
        y_test, y_pred_lgbm
    )

    return results, X_train_lgbm, X_test_lgbm


def tune_lightgbm(X_train, y_train, output_dir):

    param_dist = {
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

    base_model = LGBMClassifier(
        random_state=42,
        n_jobs=-1,
        class_weight="balanced"
    )

    tscv = TimeSeriesSplit(n_splits=5)

    search = RandomizedSearchCV(
        base_model,
        param_dist,
        n_iter=50,
        scoring="f1",
        cv=tscv,
        random_state=42,
        n_jobs=-1,
        verbose=0
    )

    search.fit(X_train, y_train)

    best_model = search.best_estimator_

    joblib.dump(best_model, os.path.join(output_dir, "lgbm_tuned_model.pkl"))

    return best_model


# =========================
# Evaluation
# =========================

def evaluate_basic(y_true, y_pred):

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist()
    }


def evaluate_full(model, X_test, y_test):

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = evaluate_basic(y_test, y_pred)

    if y_test.nunique() > 1:
        metrics["auc_roc"] = roc_auc_score(y_test, y_proba)
        precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_proba)
        metrics["auc_pr"] = auc(recall_curve, precision_curve)
    else:
        metrics["auc_roc"] = None
        metrics["auc_pr"] = None

    metrics["feature_importance"] = (
        pd.DataFrame({
            "feature": X_test.columns,
            "importance": model.feature_importances_
        })
        .sort_values("importance", ascending=False)
        .to_dict("records")
    )

    return metrics


# =========================
# Main Execution
# =========================

if __name__ == "__main__":

    DATA_PATH = "cleaned_ttc_delay_data.csv"
    OUTPUT_DIR = "model_artifacts"
    TARGET_COLUMN = "min_delay_capped"

    ensure_directory(OUTPUT_DIR)

    print("Starting TTC Delay Classification Pipeline")

    df = load_data(DATA_PATH)
    X_raw, y, cat_cols, _ = prepare_features_and_target(df, TARGET_COLUMN)

    X_encoded = encode_categorical_features(X_raw, cat_cols, OUTPUT_DIR)

    X_train, X_test, y_train, y_test = time_series_split(X_encoded, y)

    y_train_bin = create_binary_target(y_train)
    y_test_bin = create_binary_target(y_test)

    model_results, X_train_lgbm, X_test_lgbm = train_models(
        X_train,
        y_train_bin,
        X_test,
        y_test_bin,
        OUTPUT_DIR
    )

    best_lgbm = tune_lightgbm(X_train_lgbm, y_train_bin, OUTPUT_DIR)

    tuned_results = evaluate_full(best_lgbm, X_test_lgbm, y_test_bin)

    joblib.dump(
        tuned_results,
        os.path.join(OUTPUT_DIR, "tuned_lgbm_metrics.pkl")
    )

    print("Pipeline completed successfully.")
    print("Tuned LightGBM F1:", round(tuned_results["f1_score"], 4))
