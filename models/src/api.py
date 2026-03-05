"""
TTC Delay Prediction API
========================
FastAPI REST wrapper around the DelayPredictor inference engine.
This is the interface your colleague's backend calls over HTTP.

Repo path:  models/src/api.py

Run
---
    # Development
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

    # Production (via Docker / deployment)
    uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2

Endpoints
---------
    GET  /health              → service health + active model versions
    POST /predict             → single delay prediction
    POST /predict/batch       → batch predictions (multiple departure times)

Example POST /predict
---------------------
    curl -X POST http://localhost:8000/predict \
         -H "Content-Type: application/json" \
         -d '{
               "line": "Line 1",
               "station": "BLOOR STATION",
               "code": "MUSAN",
               "hour": 17,
               "day_of_week": 3,
               "is_weekend": 0,
               "month": 3,
               "week": 10,
               "year": 2026
             }'

Response schema
---------------
    {
        "delayed": true,
        "delay_probability": 0.73,
        "confidence": "high",
        "predicted_duration_minutes": 8.2,
        "duration_range": { "low": 5.3, "high": 11.1 },
        "stage1_model_version": "v20260301_120000",
        "stage2_model_version": "v20260301_121500",
        "lookup_source": "route_stats",
        "features_used": {
            "route_avg_delay": 2.86,
            "route_hour_avg_delay": 3.12,
            "route_day_hour_avg_delay": 3.47
        }
    }

Environment variables (optional overrides)
------------------------------------------
    TTC_CLF_VERSION   — pin a classification artifact version
    TTC_REG_VERSION   — pin a regression artifact version
    TTC_LOOKUP_PATH   — override path to route_stats.csv
    TTC_DELAY_THRESHOLD — probability threshold (default 0.5)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from predictor import get_predictor

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# PID file — written on startup so notifier.py can send SIGHUP for graceful reload
_PID_FILE = Path(__file__).resolve().parents[2] / "models" / "trained" / "ml_service.pid"

# ---------------------------------------------------------------------------
# Environment-driven config (so Docker / deployment can override without
# changing code)
# ---------------------------------------------------------------------------

_CLF_VERSION    = os.getenv("TTC_CLF_VERSION") or None
_REG_VERSION    = os.getenv("TTC_REG_VERSION") or None
_LOOKUP_PATH    = Path(os.getenv("TTC_LOOKUP_PATH")) if os.getenv("TTC_LOOKUP_PATH") else None
_DELAY_THRESHOLD = float(os.getenv("TTC_DELAY_THRESHOLD", "0.5"))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TTC Delay Prediction API",
    description=(
        "Two-stage ML inference service for TTC subway delay prediction. "
        "Stage 1 classifies whether a delay is likely; "
        "Stage 2 estimates its duration if so."
    ),
    version="1.0.0",
)

# Allow the chatbot backend to call this service cross-origin during dev.
# Tighten allow_origins in production to the backend's actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup — load models once
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    """
    On startup:
        1. Write the process PID to ml_service.pid so notifier.py can
           send SIGHUP for graceful reloads when a model is promoted.
        2. Load the predictor (both models + lookup table) into memory.
    """
    # Write PID file — notifier.py reads this to find the process to signal
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))
    log.info(f"ML service started (PID {os.getpid()}) — PID file: {_PID_FILE}")

    log.info("Loading ML models at startup...")
    try:
        get_predictor(
            clf_version=_CLF_VERSION,
            reg_version=_REG_VERSION,
            lookup_path=_LOOKUP_PATH,
        )
        log.info("Models loaded successfully.")
    except Exception as exc:
        log.error(f"Failed to load models at startup: {exc}")
        raise


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Remove the PID file on clean shutdown."""
    _PID_FILE.unlink(missing_ok=True)
    log.info("ML service shut down — PID file removed.")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    """
    Single prediction request.

    All fields map directly to the inputs the chatbot extracts from the
    user's message (e.g. "Will Line 1 be delayed at Bloor at 5pm on Thursday?")
    """
    line: str = Field(..., example="Line 1")
    station: str = Field(..., example="BLOOR STATION")
    code: str = Field(..., example="MUSAN",
                      description="TTC delay/event code. Pass the most common "
                                  "code for this route if unknown at query time.")
    hour: int = Field(..., ge=0, le=23, example=17)
    day_of_week: int = Field(..., ge=0, le=6, example=3,
                             description="0=Monday, 6=Sunday")
    is_weekend: int = Field(..., ge=0, le=1, example=0)
    month: int = Field(..., ge=1, le=12, example=3)
    week: int = Field(..., ge=1, le=53, example=10)
    year: int = Field(..., ge=2020, le=2035, example=2026)
    threshold: float = Field(
        default=_DELAY_THRESHOLD,
        ge=0.0, le=1.0,
        description="Probability cutoff for classifying as delayed. "
                    "Lower values increase recall (catch more real delays).",
    )

    @field_validator("line")
    @classmethod
    def validate_line(cls, v: str) -> str:
        allowed = {"Line 1", "Line 2", "Line 3", "Line 4"}
        if v not in allowed:
            raise ValueError(f"line must be one of {allowed}")
        return v


class DurationRange(BaseModel):
    low: float
    high: float


class FeaturesUsed(BaseModel):
    route_avg_delay: float
    route_hour_avg_delay: float
    route_day_hour_avg_delay: float


class PredictResponse(BaseModel):
    delayed: bool
    delay_probability: float
    confidence: str = Field(description="'high', 'medium', or 'low'")
    predicted_duration_minutes: Optional[float] = None
    duration_range: Optional[DurationRange] = None
    stage1_model_version: str
    stage2_model_version: str
    lookup_source: str
    features_used: FeaturesUsed


class BatchPredictRequest(BaseModel):
    requests: List[PredictRequest]
    threshold: float = Field(default=_DELAY_THRESHOLD, ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    status: str
    clf_version: str
    reg_version: str
    lookup_loaded: bool
    lookup_route_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> Dict[str, Any]:
    """
    Service health check. Returns active model versions and lookup table status.
    Called by load balancers and monitoring.
    """
    try:
        predictor = get_predictor()
        return predictor.health()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {exc}")


@app.get("/scheduler-status", tags=["ops"])
async def scheduler_status() -> Dict[str, Any]:
    """
    Returns the current retraining schedule config and last/next run times.
    Useful for the backend UI to show users when the model was last updated.
    """
    status_path = Path(__file__).resolve().parents[2] / "models" / "trained" / "scheduler_status.json"
    config_path = Path(__file__).resolve().parents[2] / "models" / "trained" / "scheduler_config.json"

    status = {}
    config = {}

    try:
        if status_path.exists():
            with open(status_path) as fh:
                status = json.load(fh)
        if config_path.exists():
            with open(config_path) as fh:
                config = json.load(fh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read scheduler status: {exc}")

    return {
        "schedule":        config.get("schedule", "unknown"),
        "day_of_week":     config.get("day_of_week"),
        "hour_utc":        config.get("hour"),
        "last_run_at":     status.get("last_run_at"),
        "last_run_result": status.get("last_run_result"),
        "next_run_at":     status.get("next_run_at"),
        "runs_completed":  status.get("runs_completed", 0),
        "runs_failed":     status.get("runs_failed", 0),
    }


@app.post("/predict", response_model=PredictResponse, tags=["prediction"])
async def predict(request: PredictRequest) -> Dict[str, Any]:
    """
    Predict whether a TTC subway event will result in a delay, and if so,
    how long the delay will last.

    The chatbot backend calls this with the structured information it has
    extracted from the user's natural language query.
    """
    try:
        predictor = get_predictor()
        result = predictor.predict(
            line        = request.line,
            station     = request.station,
            code        = request.code,
            hour        = request.hour,
            day_of_week = request.day_of_week,
            is_weekend  = request.is_weekend,
            month       = request.month,
            week        = request.week,
            year        = request.year,
            threshold   = request.threshold,
        )
        return result
    except Exception as exc:
        log.error(f"Prediction error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")


@app.post("/predict/batch", tags=["prediction"])
async def predict_batch(request: BatchPredictRequest) -> List[Dict[str, Any]]:
    """
    Run predictions for multiple departure times in a single call.

    Useful when the chatbot wants to show delay likelihood for the
    next 3 trains or across a range of departure times.
    """
    if len(request.requests) > 20:
        raise HTTPException(
            status_code=422,
            detail="Batch size limited to 20 requests per call.",
        )
    try:
        predictor = get_predictor()
        return predictor.predict_batch(
            [r.model_dump(exclude={"threshold"}) for r in request.requests],
            threshold=request.threshold,
        )
    except Exception as exc:
        log.error(f"Batch prediction error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {exc}")
