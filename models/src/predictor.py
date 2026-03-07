
"""
TTC Delay Predictor — Inference Engine 
=======================================
The single entry point for all ML predictions at runtime.

Repo path: models/src/predictor.py
Date: Mar 6.2026

This module is the interface between the trained models and the rest of the system (chatbot backend or REST API). It:

1. Loads trained model artifacts once at startup (not per request)
2. Constructs the full feature vector from raw chatbot inputs
3. Runs the two-stage prediction pipeline: Stage 1 -> Is a delay likely? (classification) Stage 2 -> If so, how long? (regression, only if delayed) 4. Returns a structured, serialisable result dict

USAGE - as a Python module (imported by backend)
-------------------------------------------------

from predictor import DelayPredictor predictor = DelayPredictor() # loads models once at startup

result = predictor.predict
( line = "Line 1", station = "BLOOR STATION", hour = 17, day_of_week = 3, # 0=Monday, 6=Sunday is_weekend = 0, month = 3, week = 10, year = 2026, # code is optional - omit it and the predictor infers it )

CONFIDENCE LEVELS
-----------------
high delay_probability >= 0.70 or <= 0.30
medium delay_probability in [0.45, 0.70) or (0.30, 0.45]
low delay_probability near 0.5 boundary

DELAY THRESHOLD
---------------
Default threshold is 0.5. Lower to 0.40 to increase recall for commuter-facing alerts.
"""

from __future__ import annotations
from registry import ModelRegistry
from ph1_regression import build_feature_matrix as reg_build_features
from ph1_regression import load_regressor
from ph1_classification import load_classifier
from ph1_classification import build_feature_matrix as clf_build_features
from build_lookup import DEFAULT_OUT_PATH, RouteLookup
import pandas as pd
import numpy as np
from typing import Any, Dict, Optional
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))


log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DURATION_UNCERTAINTY = 0.35
UNKNOWN_CODE = "__UNKNOWN__"


class DelayPredictor:

    def __init__(
        self,
        registry_path=None,
        lookup_path=None,
        clf_version=None,
        reg_version=None,
    ):
        self._registry = ModelRegistry(
            registry_path=registry_path or ModelRegistry.__init__.__defaults__[0])
        clf_dir = (
            _REPO_ROOT / "models" / "trained" / "classification" / clf_version
            if clf_version
            else self._registry.get_active_dir("classification")
        )
        reg_dir = (
            _REPO_ROOT / "models" / "trained" / "regression" / reg_version
            if reg_version
            else self._registry.get_active_dir("regression")
        )
        log.info(f"Loading classification model from: {clf_dir}")
        self._clf_model, self._clf_ohe, self._clf_features = load_classifier(
            clf_dir)
        self._clf_version = clf_dir.name
        log.info(f"Loading regression model from: {reg_dir}")
        self._reg_model, self._reg_ohe, self._reg_features = load_regressor(
            reg_dir)
        self._reg_version = reg_dir.name
        lp = lookup_path or DEFAULT_OUT_PATH
        log.info(f"Loading route lookup table from: {lp}")
        self._lookup = RouteLookup(stats_path=lp)
        self._default_code = self._build_default_code_index()
        log.info(f"Default codes per line: {self._default_code}")
        log.info("DelayPredictor ready.")

    def predict(
        self,
        line,
        station,
        hour,
        day_of_week,
        is_weekend,
        month,
        week,
        year,
        code=None,
        threshold=0.5,
    ):
        resolved_code = self._resolve_code(code, line)
        code_was_inferred = (code is None or code == UNKNOWN_CODE)
        route_stats = self._lookup.get(
            line, station, resolved_code, hour, day_of_week)
        raw_features = {
            "Line": line,
            "Station": station,
            "Code": resolved_code,
            "hour": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "month": month,
            "week": week,
            "year": year,
            "route_avg_delay": route_stats["route_avg_delay"],
            "route_hour_avg_delay": route_stats["route_hour_avg_delay"],
            "route_day_hour_avg_delay": route_stats["route_day_hour_avg_delay"],
        }
        raw_df = pd.DataFrame([raw_features])
        X_clf, _, _ = clf_build_features(
            raw_df, ohe=self._clf_ohe, fit_encoder=False)
        delay_prob = float(self._clf_model.predict_proba(X_clf)[0, 1])
        is_delayed = delay_prob >= threshold
        confidence = self._confidence_level(delay_prob)
        result = {
            "delayed": bool(is_delayed),
            "delay_probability": round(delay_prob, 4),
            "confidence": confidence,
            "predicted_duration_minutes": None,
            "duration_range": None,
            "code_used": resolved_code,
            "code_was_inferred": code_was_inferred,
            "stage1_model_version": self._clf_version,
            "stage2_model_version": self._reg_version,
            "lookup_source": "route_stats",
            "features_used": route_stats,
        }
        if is_delayed:
            X_reg, _, _ = reg_build_features(
                raw_df, ohe=self._reg_ohe, fit_encoder=False)
            duration = float(self._reg_model.predict(X_reg)[0])
            duration = max(0.0, round(duration, 1))
            low = round(max(0.0, duration * (1 - _DURATION_UNCERTAINTY)), 1)
            high = round(duration * (1 + _DURATION_UNCERTAINTY), 1)
            result["predicted_duration_minutes"] = duration
            result["duration_range"] = {"low": low, "high": high}
        return result

    def predict_batch(self, requests, threshold=0.5):
        return [self.predict(**req, threshold=threshold) for req in requests]

    def health(self):
        return {
            "status": "ok",
            "clf_version": self._clf_version,
            "reg_version": self._reg_version,
            "lookup_loaded": True,
            "lookup_route_count": len(self._lookup._stats),
        }

    def _build_default_code_index(self):
        stats = self._lookup._stats
        if stats.empty or "Code" not in stats.columns:
            return {"__GLOBAL__": "MUSAN"}
        index = {}
        try:
            filtered = stats[stats["Line"] != "__FALLBACK__"].copy()
            for line_name, group in filtered.groupby("Line"):
                top_code = group["Code"].value_counts().index[0]
                index[str(line_name)] = str(top_code)
        except Exception:
            pass
        try:
            global_top = (
                stats[stats["Code"] != "__FALLBACK__"]["Code"]
                .value_counts()
                .index[0]
            )
            index["__GLOBAL__"] = str(global_top)
        except Exception:
            index["__GLOBAL__"] = "MUSAN"
        return index

    def _resolve_code(self, code, line):
        if code and code not in (UNKNOWN_CODE, ""):
            return code
        try:
            result = (
                self._default_code.get(line)
                or self._default_code.get("__GLOBAL__")
                or "MUSAN"
            )
            if hasattr(result, "iloc"):
                return str(result.iloc[0])
            return str(result)
        except Exception:
            return "MUSAN"

    @staticmethod
    def _confidence_level(probability):
        distance = abs(probability - 0.5)
        if distance >= 0.20:
            return "high"
        elif distance >= 0.10:
            return "medium"
        else:
            return "low"


_predictor_instance = None


def get_predictor(clf_version=None, reg_version=None, lookup_path=None):
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = DelayPredictor(
            clf_version=clf_version,
            reg_version=reg_version,
            lookup_path=lookup_path,
        )
    return _predictor_instance
