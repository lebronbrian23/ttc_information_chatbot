"""
TTC Delay Predictor — Inference Engine
=======================================
The single entry point for all ML predictions at runtime.

Repo path:   models/src/predictor.py

This module is the interface between the trained models and the rest of the
system (chatbot backend or REST API). It:

      1. Loads trained model artifacts once at startup (not per request)
      2. Constructs the full feature vector from raw chatbot inputs
      3. Runs the two-stage prediction pipeline:
                 Stage 1 → Is a delay likely?   (classification)
                 Stage 2 → If so, how long?      (regression, only if delayed)
      4. Returns a structured, serialisable result dict

USAGE — as a Python module (imported by backend)
-------------------------------------------------
      from predictor import DelayPredictor

      predictor = DelayPredictor()               # loads models once at startup

      result = predictor.predict(
            line            = "Line 1",
            station       = "BLOOR STATION",
            code            = "MUSAN",
            hour            = 17,
            day_of_week = 3,               # 0=Monday … 6=Sunday
            is_weekend   = 0,
            month          = 3,
            week            = 10,
            year            = 2026,
      )

      # result is a plain dict — safe to serialize to JSON
      # {
      #       "delayed":                            True,
      #       "delay_probability":             0.73,
      #       "confidence":                        "high",
      #       "predicted_duration_minutes": 8.2,
      #       "duration_range":                  {"low": 5.0, "high": 12.0},
      #       "stage1_model_version":         "v20260301_120000",
      #       "stage2_model_version":         "v20260301_121500",
      #       "lookup_source":                   "route_stats",
      #       "features_used":                   { ... }
      # }

USAGE — as a REST API (run with uvicorn)
-----------------------------------------
      uvicorn api:app --host 0.0.0.0 --port 8000

      POST /predict
      {
            "line": "Line 1",
            "station": "BLOOR STATION",
            "code": "MUSAN",
            "hour": 17,
            "day_of_week": 3,
            "is_weekend": 0,
            "month": 3,
            "week": 10,
            "year": 2026
      }

CONFIDENCE LEVELS
-----------------
      high      delay_probability >= 0.70 or <= 0.30
      medium   delay_probability in [0.45, 0.70) or (0.30, 0.45]
      low       delay_probability in [0.40, 0.45) or (0.45, 0.55]
                  (model is near the decision boundary — flag for chatbot to caveat)

DELAY THRESHOLD
---------------
Default threshold is 0.5. For a commuter-facing alert system you may want
to lower this (e.g. 0.40) to increase recall — better to warn about a delay
that doesn't happen than to miss one that does. Pass threshold= to predict().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

# Internal modules
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_lookup import RouteLookup, DEFAULT_OUT_PATH
from ph1_classification import build_feature_matrix as clf_build_features
from ph1_classification import load_classifier, make_binary_target
from ph1_regression import build_feature_matrix as reg_build_features
from ph1_regression import load_regressor
from registry import ModelRegistry

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Duration uncertainty band — ± this fraction of predicted duration
_DURATION_UNCERTAINTY = 0.35

# Sentinel value used when the caller does not know the delay code.
# The predictor replaces this with the most common code for the given
# line, derived from route_stats.csv at startup.
UNKNOWN_CODE = "__UNKNOWN__"


class DelayPredictor:
      """
      Two-stage TTC delay predictor.

      Loads all artifacts once on construction. Thread-safe for concurrent
      reads (sklearn/LightGBM predict calls are thread-safe).

      Parameters
      ----------
      registry_path      : Override path to model_registry.json
      lookup_path         : Override path to route_stats.csv
      clf_version         : Pin a specific classification version (overrides registry)
      reg_version         : Pin a specific regression version (overrides registry)
      """

      def __init__(
            self,
            registry_path: Optional[Path] = None,
            lookup_path: Optional[Path] = None,
            clf_version: Optional[str] = None,
            reg_version: Optional[str] = None,
      ):
            self._registry = ModelRegistry(
                  registry_path=registry_path or ModelRegistry.__init__.__defaults__[0]
            )

            # Resolve artifact directories
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
            self._clf_model, self._clf_ohe, self._clf_features = load_classifier(clf_dir)
            self._clf_version = clf_dir.name

            log.info(f"Loading regression model from: {reg_dir}")
            self._reg_model, self._reg_ohe, self._reg_features = load_regressor(reg_dir)
            self._reg_version = reg_dir.name

            # Feature lookup table
            lp = lookup_path or DEFAULT_OUT_PATH
            log.info(f"Loading route lookup table from: {lp}")
            self._lookup = RouteLookup(stats_path=lp)

            # Build a per-line default code index: Line → most common Code
            # Used when the caller passes code=None or code=UNKNOWN_CODE.
            # This means general queries like "will Line 1 be delayed?" still
            # get a meaningful prediction rather than an error.
            self._default_code: dict[str, str] = self._build_default_code_index()
            log.info(f"Default codes per line: {self._default_code}")

            log.info("DelayPredictor ready.")

      # ------------------------------------------------------------------
      # Public API
      # ------------------------------------------------------------------

      def predict(
            self,
            line: str,
            station: str,
            hour: int,
            day_of_week: int,
            is_weekend: int,
            month: int,
            week: int,
            year: int,
            code: Optional[str] = None,
            threshold: float = 0.5,
      ) -> Dict[str, Any]:
            """
            Run the full two-stage prediction for a single request.

            Parameters
            ----------
            line            : TTC line name, e.g. "Line 1"
            station       : Station name as it appears in training data,
                                 e.g. "BLOOR STATION"
            hour            : Hour of day (0–23)
            day_of_week : Day of week (0=Monday … 6=Sunday)
            is_weekend   : 1 if Saturday or Sunday, else 0
            month          : Month (1–12)
            week            : ISO week number (1–53)
            year            : Four-digit year
            code            : TTC delay/event code, e.g. "MUSAN". Optional — if not
                                 provided or not known at query time (which is the normal
                                 case for user-facing queries), the predictor substitutes
                                 the most common code for this line from training data.
                                 The resolved code is reported in the result under
                                 "code_used" so the LLM layer can see what was assumed.
            threshold    : Probability cutoff for classifying as delayed.
                                 Default 0.5. Lower to increase recall (recommended
                                 for user-facing delay alerts).

            Returns
            -------
            Plain dict — all values are JSON-serialisable.
            See module docstring for full schema.
            """
            # ── Resolve code ──────────────────────────────────────────────────
            # code is optional at the API level because users don't know TTC
            # internal codes. Fall back to the most common code for this line.
            resolved_code = self._resolve_code(code, line)
            code_was_inferred = (code is None or code == UNKNOWN_CODE)

            # ── Build raw feature row ─────────────────────────────────────────
            route_stats = self._lookup.get(
                  line, station, resolved_code, hour, day_of_week
            )

            raw_features = {
                  "Line":                               line,
                  "Station":                           station,
                  "Code":                               resolved_code,
                  "hour":                               hour,
                  "day_of_week":                     day_of_week,
                  "is_weekend":                      is_weekend,
                  "month":                              month,
                  "week":                               week,
                  "year":                               year,
                  "route_avg_delay":               route_stats["route_avg_delay"],
                  "route_hour_avg_delay":       route_stats["route_hour_avg_delay"],
                  "route_day_hour_avg_delay": route_stats["route_day_hour_avg_delay"],
            }

            raw_df = pd.DataFrame([raw_features])

            # ── Stage 1: Classification ───────────────────────────────────────
            X_clf, _, _ = clf_build_features(raw_df, ohe=self._clf_ohe, fit_encoder=False)
            delay_prob   = float(self._clf_model.predict_proba(X_clf)[0, 1])
            is_delayed   = delay_prob >= threshold
            confidence   = self._confidence_level(delay_prob)

            result: Dict[str, Any] = {
                  "delayed":                              bool(is_delayed),
                  "delay_probability":               round(delay_prob, 4),
                  "confidence":                         confidence,
                  "predicted_duration_minutes": None,
                  "duration_range":                   None,
                  "code_used":                           resolved_code,
                  "code_was_inferred":               code_was_inferred,
                  "stage1_model_version":          self._clf_version,
                  "stage2_model_version":          self._reg_version,
                  "lookup_source":                     "route_stats",
                  "features_used":                     route_stats,
            }

            # ── Stage 2: Regression (only when delay predicted) ───────────────
            if is_delayed:
                  X_reg, _, _ = reg_build_features(
                        raw_df, ohe=self._reg_ohe, fit_encoder=False
                  )
                  duration = float(self._reg_model.predict(X_reg)[0])
                  duration = max(0.0, round(duration, 1))

                  low   = round(max(0.0, duration * (1 - _DURATION_UNCERTAINTY)), 1)
                  high = round(duration * (1 + _DURATION_UNCERTAINTY), 1)

                  result["predicted_duration_minutes"] = duration
                  result["duration_range"] = {"low": low, "high": high}

            log.debug(
                  f"predict({line}, {station}, code={resolved_code}, "
                  f"h={hour}, dow={day_of_week}) "
                  f"→ delayed={is_delayed} p={delay_prob:.3f} "
                  f"duration={result['predicted_duration_minutes']}"
            )

            return result

      def predict_batch(
            self,
            requests: list[dict],
            threshold: float = 0.5,
      ) -> list[Dict[str, Any]]:
            """
            Run predictions for multiple requests.

            Each item in requests must be a dict with the same keys as the
            keyword arguments of predict(). Returns a list of result dicts
            in the same order.

            Useful for pre-computing predictions for a set of upcoming
            departure times (e.g. "next 3 trains").
            """
            return [self.predict(**req, threshold=threshold) for req in requests]

      def health(self) -> Dict[str, Any]:
            """
            Return a health-check payload.
            Called by the API's /health endpoint and by monitoring.
            """
            return {
                  "status":                     "ok",
                  "clf_version":             self._clf_version,
                  "reg_version":             self._reg_version,
                  "lookup_loaded":          True,
                  "lookup_route_count":   len(self._lookup._stats),
            }

      # ------------------------------------------------------------------
      # Internal helpers
      # ------------------------------------------------------------------

      def _build_default_code_index(self) -> dict[str, str]:
            """
            Build a Line → most_common_Code mapping from the lookup table.
            Used to substitute a sensible code when the caller doesn't provide one.
            Falls back to the global most common code if a line has no data.
            """
            stats = self._lookup._stats
            if stats.empty or "Code" not in stats.columns:
                  return {}

            # Count occurrences of each (Line, Code) combination and take the top
            # code per line. route_stats has one row per unique combination so
            # row count serves as a reasonable frequency proxy.
            try:
                  top_codes = (
                        stats[stats["Line"] != "__FALLBACK__"]
                        .groupby(["Line", "Code"])
                        .size()
                        .reset_index(name="count")
                        .sort_values("count", ascending=False)
                        .groupby("Line")
                        .first()
                        .reset_index()[["Line", "Code"]]
                  )
                  index = dict(zip(top_codes["Line"], top_codes["Code"]))
            except Exception:
                  index = {}

            # Global fallback: most common code across all lines
            try:
                  global_top = (
                        stats[stats["Code"] != "__FALLBACK__"]
                        ["Code"]
                        .value_counts()
                        .index[0]
                  )
                  index["__GLOBAL__"] = global_top
            except Exception:
                  index["__GLOBAL__"] = "MUSAN"    # hard fallback

            return index

      def _resolve_code(self, code: Optional[str], line: str) -> str:
            """
            Return a usable TTC delay code.

            Resolution order:
                  1. Use the caller-supplied code if it is a real value
                  2. Use the most common code for this line from training data
                  3. Use the most common code across all lines
                  4. Hard fallback: "MUSAN"
            """
            if code and code not in (UNKNOWN_CODE, ""):
                  return code

            return (
                  self._default_code.get(line)
                  or self._default_code.get("__GLOBAL__")
                  or "MUSAN"
            )

      @staticmethod
      def _confidence_level(probability: float) -> str:
            """
            Map a delay probability to a human-readable confidence level.

            high    → model is confident (probability far from 0.5)
            medium → model has reasonable signal
            low      → model is near the decision boundary; chatbot should caveat
            """
            distance = abs(probability - 0.5)
            if distance >= 0.20:
                  return "high"
            elif distance >= 0.10:
                  return "medium"
            else:
                  return "low"


# ---------------------------------------------------------------------------
# Module-level singleton — used by api.py and direct imports
# ---------------------------------------------------------------------------
# Instantiated lazily on first access so the module can be imported without
# immediately requiring trained artifacts to be present (useful in tests).

_predictor_instance: Optional[DelayPredictor] = None


def get_predictor(
      clf_version: Optional[str] = None,
      reg_version: Optional[str] = None,
      lookup_path: Optional[Path] = None,
) -> DelayPredictor:
      """
      Return the module-level singleton DelayPredictor, creating it on first
      call. Subsequent calls return the cached instance.

      Pass clf_version / reg_version to pin specific model versions.
      If not passed, the registry's active versions are used.

      This is the recommended way to access the predictor from api.py and
      from the chatbot backend — it ensures models are loaded only once.
      """
      global _predictor_instance
      if _predictor_instance is None:
            _predictor_instance = DelayPredictor(
                  clf_version=clf_version,
                  reg_version=reg_version,
                  lookup_path=lookup_path,
            )
      return _predictor_instance
