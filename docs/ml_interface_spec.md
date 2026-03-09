# ML Layer Interface Specification

> **Purpose:** This document defines the contract between the ML prediction layer and the NLP/Backend layers. All three teams should treat this as the source of truth for integration.
>
> Version 1 | March 2026

> **Important:** This is a PREDICTIVE system based on historical delay patterns. It does not provide live service status. Direct users to TTC service alerts for real-time information.

---

## Contents

1. [System Architecture](#1-system-architecture)
2. [Calling the ML Layer](#2-calling-the-ml-layer)
3. [Input Fields Reference](#3-input-fields-reference)
4. [The code Field](#4-the-code-field)
5. [Response Schema](#5-response-schema)
6. [Station Names](#6-station-names)
7. [Threshold](#7-threshold)
8. [Confidence Level Language Guide](#8-confidence-level-language-guide)
9. [Batch Predictions](#9-batch-predictions)
10. [Health Check](#10-health-check)
11. [Error Responses (REST API)](#11-error-responses-rest-api)
12. [NLP Layer Responsibilities](#12-nlp-layer-responsibilities)
13. [Backend Layer Responsibilities](#13-backend-layer-responsibilities)
14. [Model Performance Reference](#14-model-performance-reference)

---

## 1. System Architecture

The ML layer sits between the NLP layer and the training data. It accepts structured inputs and returns structured predictions. It does no natural language processing.

```
User message (natural language)
        |
        v
+----------------------------------+
|        NLP / LLM Layer           |
|  - Intent detection              |
|  - Entity extraction             |
|  - Multi-turn memory             |
|  - Response generation           |
+----------------+-----------------+
                 | structured request (HTTP POST or Python import)
                 v
+----------------------------------+
|      ML Prediction Layer         |
|    predictor.py / api.py         |
|  - Feature construction          |
|  - Stage 1: delay classification |
|  - Stage 2: duration regression  |
+----------------+-----------------+
                 | structured result dict
                 v
        NLP layer (response generation)
        Backend layer (logging, routing)
```

---

## 2. Calling the ML Layer

Two integration options are available. Discuss with the team which fits your architecture.

### Option A — Direct Python Import (same service)

```python
from predictor import get_predictor

# Call once at startup, NOT per request
predictor = get_predictor()

result = predictor.predict(
    line        = "Line 1",
    station     = "BLOOR STATION",
    hour        = 17,
    day_of_week = 3,
    is_weekend  = 0,
    month       = 3,
    week        = 10,
    year        = 2026,
    # code is optional - see Section 4
)
```

### Option B — REST API (separate service)

```
POST http://localhost:8000/predict
Content-Type: application/json

{
    "line":        "Line 1",
    "station":     "BLOOR STATION",
    "hour":        17,
    "day_of_week": 3,
    "is_weekend":  0,
    "month":       3,
    "week":        10,
    "year":        2026
}
```

> **Note:** The API runs on port 8000. In Codespaces, forward this port via the Ports tab. In production, update the base URL to match your deployment.

---

## 3. Input Fields Reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `line` | string | Yes | One of: `Line 1`, `Line 2`, `Line 3`, `Line 4` |
| `station` | string | Yes | Uppercase, e.g. `BLOOR STATION`. See Section 6. |
| `hour` | int 0–23 | Yes | Hour of day in 24h format |
| `day_of_week` | int 0–6 | Yes | 0=Monday, 1=Tuesday, ... 6=Sunday |
| `is_weekend` | int 0 or 1 | Yes | 1 if Saturday or Sunday, else 0 |
| `month` | int 1–12 | Yes | Calendar month |
| `week` | int 1–53 | Yes | ISO week number |
| `year` | int | Yes | Four-digit year |
| `code` | string | No | TTC delay code. Omit in most cases — ML layer infers it. See Section 4. |
| `threshold` | float 0–1 | No | Default 0.5. Lower to 0.40 for higher recall. See Section 7. |

---

## 4. The code Field

The ML model was trained with TTC internal delay codes as a feature. Users will never say these codes.

**You do not need to extract or pass `code` in most cases.**

When `code` is omitted, the ML layer automatically substitutes the most common delay code historically seen on that line. The inferred code per line from training data is:

| Line | Default Inferred Code |
|---|---|
| Line 1 | SUDP |
| Line 2 | SUDP |
| Line 1/2 | MUO |
| Line 4 | PUOPO |

The result always reports what code was used:

```json
"code_used": "SUDP",
"code_was_inferred": true
```

The only case to pass `code` is if TTC publishes a live service alert with a specific code and the backend has access to it. Otherwise omit it.

---

## 5. Response Schema

```json
{
    "delayed":                    true,
    "delay_probability":          0.63,
    "confidence":                 "medium",
    "predicted_duration_minutes": 7.2,
    "duration_range":             { "low": 4.7, "high": 9.7 },
    "code_used":                  "SUDP",
    "code_was_inferred":          true,
    "stage1_model_version":       "v20260307_055529",
    "stage2_model_version":       "v20260307_065006",
    "lookup_source":              "route_stats",
    "features_used": {
        "route_avg_delay":          1.43,
        "route_hour_avg_delay":     2.04,
        "route_day_hour_avg_delay": 4.0
    }
}
```

### Field Descriptions

| Field | Type | Description |
|---|---|---|
| `delayed` | boolean | Whether a delay is predicted. Use as the top-level answer. |
| `delay_probability` | float | Raw model probability. Only show to user when confidence is `high` or `medium`. |
| `confidence` | high/medium/low | How far probability is from 0.5. Most important field for response phrasing. See Section 8. |
| `predicted_duration_minutes` | float or null | Point estimate of delay duration. Null when `delayed` is false. |
| `duration_range` | object or null | `low`/`high` bounds at ±35%. Always present alongside duration, never alone. |
| `code_used` | string | The delay code used. Do not surface to user unless they ask. |
| `code_was_inferred` | boolean | True when ML layer chose the code. Add a caveat like *based on typical delays on this line*. |
| `stage1_model_version` | string | Classification model version. Log this per request for traceability. |
| `stage2_model_version` | string | Regression model version. Log this per request for traceability. |
| `features_used` | object | The three historical averages used. Optional to surface — useful for explaining predictions. |

---

## 6. Station Names

Station names must match the training data exactly — uppercase with `STATION` suffix.

| User says | Pass to ML layer as |
|---|---|
| Bloor | `BLOOR STATION` |
| Spadina | `SPADINA STATION` |
| Union | `UNION STATION` |
| Sheppard-Yonge | `SHEPPARD-YONGE STATION` |

The full list of valid station names is in:

```
data/processing/route_stats.csv  →  Station column
```

If a station still does not match after normalisation, the ML layer falls back to global averages and will not error. The result is still valid but less accurate — add a caveat in the response.

> **Note:** Station name normalisation is recommended to be owned by the NLP layer since it has the language context to resolve ambiguous names.

---

## 7. Threshold

The default threshold (0.5) means the model predicts `delayed` when it assigns more than 50% probability.

**Recommendation: lower to 0.40 for a commuter-facing chatbot.**

Missing a real delay is worse for a commuter than being warned of one that does not happen. At 0.40, the model catches more real delays at the cost of more false alarms.

To set per request:

```json
{ "...", "threshold": 0.40 }
```

---

## 8. Confidence Level Language Guide

The `confidence` field should directly control how the chatbot phrases its answer. This is the most important section for NLP prompt design.

### confidence: high

The model is confident. State the prediction clearly.

> *"There is a 73% chance of delays on Line 1 at Bloor Station around 5pm Thursday. If delayed, expect around 8 minutes (typically between 5 and 11 minutes)."*

### confidence: medium

The model has signal but is not highly confident. Add a light hedge.

> *"There is a moderate chance of delays (~58%) on Line 1 at Bloor around 5pm Thursday, though it is not certain. If delays occur, they tend to last around 8 minutes."*

### confidence: low

The model is near the decision boundary — its prediction is unreliable. Do not state a probability. Acknowledge uncertainty.

> *"The model does not have strong signal for this particular route and time. Based on general patterns, delays are possible but I cannot give a reliable estimate. I would suggest checking TTC service alerts directly."*

---

## 9. Batch Predictions

For comparative questions (*Should I leave now or in 30 minutes?*), use the batch endpoint rather than multiple single calls.

```
POST http://localhost:8000/predict/batch

{
    "requests": [
        { "line": "Line 1", "station": "BLOOR STATION", "hour": 17, "..." },
        { "line": "Line 1", "station": "BLOOR STATION", "hour": 18, "..." }
    ],
    "threshold": 0.5
}
```

The response is a list of result dicts in the same order. Compare `delay_probability` across results to recommend the better departure time.

**Batch size limit: 20 requests per call.**

---

## 10. Health Check

Before making prediction calls, verify the ML service is up:

```
GET http://localhost:8000/health
```

Response:

```json
{
    "status":             "ok",
    "clf_version":        "v20260307_055529",
    "reg_version":        "v20260307_065006",
    "lookup_loaded":      true,
    "lookup_route_count": 33925
}
```

If `status` is not `ok`, treat all prediction responses as unreliable and fall back to directing the user to live TTC service alerts.

---

## 11. Error Responses (REST API)

| HTTP Status | Meaning | What to do |
|---|---|---|
| 200 | Success | Use the result normally |
| 422 | Invalid input (bad line name, out-of-range hour) | Check entity extraction — something was passed incorrectly |
| 500 | Prediction failed unexpectedly | Log and fall back to TTC service alerts |
| 503 | Service unavailable — models not loaded | Retry once after 2 seconds, then fall back |

---

## 12. NLP Layer Responsibilities

The ML layer does none of the following — these are entirely the NLP layer's concern:

- Detecting that a user message is a delay prediction query vs. a schedule question, route planning question, or general TTC question
- Extracting line, station, and time from natural language — for example *around rush hour* maps to `hour=17`, *this Thursday* maps to `day_of_week=3`
- Handling ambiguity — for example *Bloor* should confirm: Bloor-Yonge or Bloor-Christie?
- Multi-turn context — for example *What about tomorrow?* means apply the same line/station with updated day/time
- Formatting the result dict into a natural language response using the confidence language guide in Section 8
- Deciding when to add caveats — for example when `code_was_inferred` is true or `confidence` is low
- Falling back gracefully when the ML service is unavailable (HTTP 503)
- Deriving `is_weekend`, `week`, and `month` from the user's time context before calling the ML layer

---

## 13. Backend Layer Responsibilities

The backend layer sits between the user interface and both the NLP and ML layers. Its ML-related responsibilities are:

### Routing and Orchestration

- Route prediction requests from the frontend to the NLP layer
- Do not call the ML layer directly — let the NLP layer handle that after entity extraction
- If using the REST API option, proxy calls to the ML service and handle timeouts

### Logging (important for model monitoring)

Log the following fields from every prediction response to your database or log store:

```
stage1_model_version
stage2_model_version
delay_probability
confidence
code_was_inferred
timestamp of request
line and station that were queried
```

> **Note:** This logging is essential for future model evaluation. When real delay outcomes become available they can be matched against these logged predictions to measure real-world accuracy.

### Model Update Notifications

When the ML layer retrains and promotes new models, it sends a webhook `POST` to registered URLs. The backend should register its URL in:

```
models/trained/webhook_subscribers.json
```

The notification payload is:

```json
{
    "event":                   "model_promoted",
    "classification_version":  "v20260307_055529",
    "regression_version":      "v20260307_065006",
    "promoted_at":             "2026-03-07T06:00:00Z"
}
```

On receiving this webhook, the backend should:

- Log the new model versions
- Optionally notify the NLP layer to reload its predictor instance
- No restart is required — the ML service reloads models automatically via SIGHUP

### Health Monitoring

Poll `GET /health` on the ML service periodically (e.g. every 60 seconds). If `status` is not `ok`, surface a fallback message to users rather than calling `/predict`.

### Service URL Configuration

The ML service URL should be an environment variable, not hardcoded:

```bash
ML_SERVICE_URL=http://localhost:8000        # local / Codespaces
ML_SERVICE_URL=https://your-deployment-url  # production
```

---

## 14. Model Performance Reference

Actual metrics from the production training run (March 2026). Share these with your team so responses are calibrated to real model capability.

### Classification Model (delay vs no delay)

| Metric | Value | What it means |
|---|---|---|
| Recall | 0.887 | Catches 89% of real delays — good for commuter alerts |
| Precision | 0.625 | 37% of delay alerts are false alarms — acceptable |
| F1 Score | 0.733 | Balance of precision and recall |
| AUC-ROC | 0.888 | Strong overall discrimination ability |

### Regression Model (delay duration in minutes)

| Metric | Value | What it means |
|---|---|---|
| MAE | 3.8 min | On average, duration estimate is off by 3.8 minutes |
| RMSE | 6.4 min | Beats mean baseline (7.1 min) and median baseline (7.3 min) |
| R² | 0.183 | Explains 18% of duration variance — duration is inherently noisy |

> **Note:** Duration prediction is harder than classification. Always present duration as a range (`duration_range`), never as a precise figure. The ±35% uncertainty band is intentional.
