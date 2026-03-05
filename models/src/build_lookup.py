"""
TTC Feature Lookup Table Builder
=================================
Computes historical average delay statistics from the training data and
saves them as a lightweight CSV that the inference predictor queries at
runtime to reconstruct the engineered features.

Repo path:   models/src/build_lookup.py
Output:       data/processing/route_stats.csv

WHY THIS EXISTS
---------------
The classification and regression models were trained on three engineered
features that summarise historical delay behaviour:

      route_avg_delay               — mean delay for this Line/Station/Code combination
      route_hour_avg_delay       — mean delay for this combination at this hour
      route_day_hour_avg_delay — mean delay for this combination on this
                                               day-of-week at this hour

At training time these were pre-computed in the preprocessing notebook and
stored in the CSV. At inference time (when the chatbot asks "will Line 1
be delayed at 5pm on Thursday?") we do NOT have pre-computed values —
we need to look them up from a stored table.

This script computes those statistics from the training split only
(the first 80% of data by date) to prevent leakage from test data.

DESIGN FOR FUTURE DB MIGRATION
-------------------------------
The lookup table is intentionally kept as a flat CSV so it can be swapped
for a database query later without changing predictor.py. The Lookup class
exposes a single .get() method — change the implementation behind that
interface and the predictor is unaffected.

Usage
-----
      # Run once after training, before starting the inference service
      python build_lookup.py

      # Override data path
      python build_lookup.py --data path/to/cleaned_ttc_delay_data.csv

      # Override output path
      python build_lookup.py --out path/to/route_stats.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH: Path = _REPO_ROOT / "data" / "processing" / "cleaned_ttc_delay_data.csv"
DEFAULT_OUT_PATH: Path   = _REPO_ROOT / "data" / "processing" / "route_stats.csv"

TARGET_COL:    str = "min_delay_capped"
DATE_COL:       str = "Date"
TRAIN_RATIO: float = 0.8

# Granularity levels — must match what the training notebook computed
ROUTE_KEY               = ["Line", "Station", "Code"]
ROUTE_HOUR_KEY       = ["Line", "Station", "Code", "hour"]
ROUTE_DAY_HOUR_KEY = ["Line", "Station", "Code", "day_of_week", "hour"]


def build_lookup_table(data_path: Path, out_path: Path) -> pd.DataFrame:
      """
      Compute route statistics from the training split and write to CSV.

      Returns the stats DataFrame.
      """
      log.info(f"Loading data from {data_path}")
      df = pd.read_csv(data_path, parse_dates=[DATE_COL])
      df = df.sort_values(DATE_COL).reset_index(drop=True)

      # Use training split only — identical boundary to the training pipeline
      split_idx = int(len(df) * TRAIN_RATIO)
      train_df = df.iloc[:split_idx].copy()
      log.info(
            f"Computing statistics on training split only "
            f"({len(train_df):,} rows — prevents leakage from test data)"
      )

      # ── route_avg_delay ───────────────────────────────────────────────────
      route_avg = (
            train_df.groupby(ROUTE_KEY)[TARGET_COL]
            .mean()
            .reset_index()
            .rename(columns={TARGET_COL: "route_avg_delay"})
      )

      # ── route_hour_avg_delay ──────────────────────────────────────────────
      route_hour_avg = (
            train_df.groupby(ROUTE_HOUR_KEY)[TARGET_COL]
            .mean()
            .reset_index()
            .rename(columns={TARGET_COL: "route_hour_avg_delay"})
      )

      # ── route_day_hour_avg_delay ──────────────────────────────────────────
      route_day_hour_avg = (
            train_df.groupby(ROUTE_DAY_HOUR_KEY)[TARGET_COL]
            .mean()
            .reset_index()
            .rename(columns={TARGET_COL: "route_day_hour_avg_delay"})
      )

      # Merge all three into a single lookup table
      stats = route_avg.copy()
      stats = stats.merge(route_hour_avg, on=ROUTE_KEY, how="left")
      stats = stats.merge(route_day_hour_avg, on=ROUTE_KEY, how="left")

      # Global fallback values (used when a combination is unseen at inference)
      global_avg               = float(train_df[TARGET_COL].mean())
      global_hour_avg       = global_avg
      global_day_hour_avg = global_avg

      log.info(
            f"Global fallback delay average: {global_avg:.2f} min "
            f"(used for unseen route/time combinations at inference)"
      )

      # Save fallbacks as a separate single-row sentinel in the CSV
      # so the Lookup class can read them without needing the raw data
      fallback_row = pd.DataFrame([{
            "Line":                              "__FALLBACK__",
            "Station":                         "__FALLBACK__",
            "Code":                              "__FALLBACK__",
            "hour":                              -1,
            "day_of_week":                   -1,
            "route_avg_delay":             global_avg,
            "route_hour_avg_delay":      global_hour_avg,
            "route_day_hour_avg_delay": global_day_hour_avg,
      }])

      # Compute per-hour and per-day-hour global averages for smarter fallback
      global_hour_avgs = (
            train_df.groupby("hour")[TARGET_COL]
            .mean()
            .reset_index()
            .rename(columns={TARGET_COL: "global_hour_avg"})
      )
      global_day_hour_avgs = (
            train_df.groupby(["day_of_week", "hour"])[TARGET_COL]
            .mean()
            .reset_index()
            .rename(columns={TARGET_COL: "global_day_hour_avg"})
      )

      # Persist main stats
      out_path.parent.mkdir(parents=True, exist_ok=True)
      stats.to_csv(out_path, index=False)
      log.info(f"Route stats saved: {out_path} ({len(stats):,} rows)")

      # Persist global fallback tables alongside
      hour_out = out_path.parent / "global_hour_stats.csv"
      day_hour_out = out_path.parent / "global_day_hour_stats.csv"
      global_hour_avgs.to_csv(hour_out, index=False)
      global_day_hour_avgs.to_csv(day_hour_out, index=False)
      log.info(f"Global hour stats saved:       {hour_out}")
      log.info(f"Global day-hour stats saved: {day_hour_out}")

      return stats


# ---------------------------------------------------------------------------
# Lookup class — used by predictor.py at inference time
# ---------------------------------------------------------------------------

class RouteLookup:
      """
      Lightweight feature store for inference-time feature construction.

      Loads the pre-computed route statistics once at service startup and
      exposes a single .get() method that the predictor calls per request.

      Fallback hierarchy (when an exact combination is not in the table):
            1. route + hour match   (drop Code specificity)
            2. global hour average   (drop route specificity)
            3. global overall average   (last resort)

      This is intentionally simple. When you migrate to a live database,
      replace the __init__ loading logic and _lookup_* methods — the .get()
      interface stays the same so predictor.py needs no changes.

      Parameters
      ----------
      stats_path       : Path to route_stats.csv (output of build_lookup.py)
      hour_path         : Path to global_hour_stats.csv
      day_hour_path   : Path to global_day_hour_stats.csv
      """

      def __init__(
            self,
            stats_path: Path = DEFAULT_OUT_PATH,
            hour_path: Path | None = None,
            day_hour_path: Path | None = None,
      ):
            if not stats_path.exists():
                  raise FileNotFoundError(
                        f"Route stats not found at {stats_path}.\n"
                        f"Run: python build_lookup.py"
                  )

            self._stats = pd.read_csv(stats_path)

            # Build fast-lookup indices
            self._route_idx = self._stats.set_index(
                  ["Line", "Station", "Code"]
            )
            self._route_hour_idx = self._stats.dropna(subset=["hour"]).set_index(
                  ["Line", "Station", "Code", "hour"]
            ) if "hour" in self._stats.columns else pd.DataFrame()

            # Global fallback tables
            _hour_path = hour_path or stats_path.parent / "global_hour_stats.csv"
            _day_hour_path = day_hour_path or stats_path.parent / "global_day_hour_stats.csv"

            self._global_hour: dict[int, float] = {}
            self._global_day_hour: dict[tuple, float] = {}
            self._global_avg: float = float(
                  self._stats["route_avg_delay"].mean()
            )

            if _hour_path.exists():
                  gh = pd.read_csv(_hour_path)
                  self._global_hour = dict(
                        zip(gh["hour"].astype(int), gh["global_hour_avg"])
                  )

            if _day_hour_path.exists():
                  gdh = pd.read_csv(_day_hour_path)
                  self._global_day_hour = {
                        (int(r["day_of_week"]), int(r["hour"])): r["global_day_hour_avg"]
                        for _, r in gdh.iterrows()
                  }

            log.info(
                  f"RouteLookup loaded: {len(self._stats):,} route combinations | "
                  f"global avg delay: {self._global_avg:.2f} min"
            )

      def get(
            self,
            line: str,
            station: str,
            code: str,
            hour: int,
            day_of_week: int,
      ) -> dict[str, float]:
            """
            Return the three engineered delay features for this combination.

            Always returns a complete dict — falls back gracefully for unseen
            combinations so the predictor never raises a KeyError.

            Returns
            -------
            {
                  "route_avg_delay":               float,
                  "route_hour_avg_delay":       float,
                  "route_day_hour_avg_delay": float,
            }
            """
            return {
                  "route_avg_delay":               self._get_route_avg(line, station, code),
                  "route_hour_avg_delay":       self._get_route_hour_avg(line, station, code, hour),
                  "route_day_hour_avg_delay": self._get_route_day_hour_avg(
                        line, station, code, day_of_week, hour
                  ),
            }

      # ------------------------------------------------------------------
      # Internal lookup methods — replace these when migrating to a DB
      # ------------------------------------------------------------------

      def _get_route_avg(self, line: str, station: str, code: str) -> float:
            try:
                  return float(
                        self._route_idx.loc[(line, station, code), "route_avg_delay"]
                  )
            except KeyError:
                  return self._global_avg

      def _get_route_hour_avg(
            self, line: str, station: str, code: str, hour: int
      ) -> float:
            # Try exact route + hour match
            try:
                  subset = self._stats[
                        (self._stats["Line"] == line)
                        & (self._stats["Station"] == station)
                        & (self._stats["Code"] == code)
                        & (self._stats["hour"] == hour)
                  ]
                  if not subset.empty:
                        return float(subset["route_hour_avg_delay"].iloc[0])
            except Exception:
                  pass

            # Fall back to global hour average
            return self._global_hour.get(hour, self._global_avg)

      def _get_route_day_hour_avg(
            self,
            line: str,
            station: str,
            code: str,
            day_of_week: int,
            hour: int,
      ) -> float:
            # Try exact route + day + hour match
            try:
                  subset = self._stats[
                        (self._stats["Line"] == line)
                        & (self._stats["Station"] == station)
                        & (self._stats["Code"] == code)
                        & (self._stats["day_of_week"] == day_of_week)
                        & (self._stats["hour"] == hour)
                  ]
                  if not subset.empty:
                        return float(subset["route_day_hour_avg_delay"].iloc[0])
            except Exception:
                  pass

            # Fall back to global day+hour average
            return self._global_day_hour.get(
                  (day_of_week, hour),
                  self._global_hour.get(hour, self._global_avg),
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
      logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
      )

      parser = argparse.ArgumentParser(
            description="Build route statistics lookup table for TTC inference"
      )
      parser.add_argument(
            "--data",
            type=Path,
            default=DEFAULT_DATA_PATH,
            help="Path to cleaned_ttc_delay_data.csv",
      )
      parser.add_argument(
            "--out",
            type=Path,
            default=DEFAULT_OUT_PATH,
            help="Output path for route_stats.csv",
      )
      args = parser.parse_args()

      build_lookup_table(data_path=args.data, out_path=args.out)
      log.info("Lookup table build complete.")
