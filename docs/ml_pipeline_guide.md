
# TTC DELAY PREDICTION CHATBOT
## ML Pipeline Guide
### Phase 1 — Delay Classification & Duration Prediction

*For: ML Engineer + Teammates (NLP/LLM & Backend)*

---

## 0. Overview & Architecture

This document covers every step required to take the ML prediction system from code to a live, automatically retraining production deployment. It is written primarily for the ML engineer and includes notes for the NLP/LLM and backend teammates where their work intersects.

> **TIP** Each file listed in this guide is already written and ready to copy into the repository. No code needs to be written from scratch.

### System Architecture

The system has three layers. The ML engineer owns the middle layer:

- **1. NLP / LLM Layer** → extracts structured inputs from user messages, generates natural language responses
- **2. ML Prediction Layer** → training, inference, scheduling, notifications
- **3. Backend / Frontend Layer** → serves the chatbot UI, calls the ML API

### Repository Ownership

Each layer of the system owns its own folder. Team members should not put code in folders outside their domain:

```
ttc_information_chatbot/
├── models/          ← ML engineer only (you)
│   ├── src/         ← all ML source code
│   ├── trained/     ← generated artifacts
│   └── experiments/
├── nlp/             ← NLP/LLM colleague only
│   └── (they structure internally)
├── backend/         ← backend colleague only
├── frontend/        ← frontend colleague only
├── data-pipeline/   ← NLP colleague (they own data ingestion too)
│   └── (ingestion, cleaning, transformation scripts)
├── data-model/      ← backend colleague most likely
│   └── (database schemas, migrations)
├── notebooks/       ← SHARED, anyone — exploration only, never production code
├── tests/           ← SHARED, everyone adds their own
│   ├── test_models/ ← your tests
│   ├── test_nlp/    ← NLP colleague's tests
│   └── test_backend/← backend colleague's tests
├── logs/
├── .gitignore
├── requirements.txt
└── README.md
```

> **NOTE** `notebooks/` is for exploration and experimentation only. Production code lives in `models/src/`, not in notebooks. This is the rule most commonly broken on team projects.

### Complete File List

All files belong in `models/src/` unless noted:

| File | Location | Purpose |
|------|----------|---------|
| `ph1_classification.py` | `models/src/` | Training pipeline — binary delay classifier |
| `ph1_regression.py` | `models/src/` | Training pipeline — delay duration regressor |
| `build_lookup.py` | `models/src/` | Builds route_stats.csv for inference-time features |
| `registry.py` | `models/src/` | Manages which trained artifact version is active |
| `predictor.py` | `models/src/` | Core inference engine — called per user request |
| `api.py` | `models/src/` | FastAPI REST wrapper around predictor |
| `notifier.py` | `models/src/` | Sends webhooks + triggers graceful service restart |
| `retrain.sh` | `models/src/` | Shell script — runs the full retrain pipeline |
| `scheduler.py` | `models/src/` | Runs retrain.sh on a weekly/monthly/on-demand schedule |
| `ml_interface_spec.docx` | `docs/` | Interface contract between ML and NLP/backend layers |
| `route_stats.csv` | `data/processing/` | Generated — do not edit manually |
| `model_registry.json` | `models/trained/` | Generated — do not edit manually |
| `webhook_subscribers.json` | `models/trained/` | Register backend + NLP webhook endpoints here |
| `ml_service.pid` | `models/trained/` | Generated at runtime — do not edit or commit |

---

## 0.1 How the Components Connect

The file table above lists what each file does in isolation. This section explains how they relate to each other and why the system is structured the way it is.

### The three execution tiers

Not all files run at the same time. Understanding when each file runs is the key to understanding the whole system:

```
OFFLINE — runs on a schedule, not during user requests
─────────────────────────────────────────────────────────────────────
ph1_classification.py   Runs when you retrain (weekly/monthly)
ph1_regression.py       Runs when you retrain (weekly/monthly)
build_lookup.py         Runs after every retrain (route stats update)
registry.py promote     Runs after every retrain (promotes new version)

ONCE AT SERVICE STARTUP — runs when the server boots, not per request
─────────────────────────────────────────────────────────────────────
predictor.py            Models loaded into memory on startup
api.py                  FastAPI app initialises, calls get_predictor()
registry.py (read)      Reads which artifact version is currently active

PER USER REQUEST — runs every time someone asks a question
─────────────────────────────────────────────────────────────────────
predictor.predict()     Feature construction + model.predict_proba()
                        This takes milliseconds
```

This design matters for performance. A LightGBM model trained on 874 features is large. Loading it from disk on every chatbot message would make the service unusably slow. The `get_predictor()` singleton at the bottom of `predictor.py` exists specifically to ensure models are loaded exactly once at startup, no matter how many requests come in.

### File dependency order

The files depend on each other in a strict build order:

```
registry.py         ← needed by everything else; establishes which versions are live
     ↓
build_lookup.py     ← produces route_stats.csv that predictor depends on
     ↓
predictor.py        ← depends on registry (to find model artifacts) + lookup (for features)
     ↓
api.py              ← thin wrapper; depends only on predictor
```

`retrain.sh` encodes this order explicitly — it calls the training scripts in sequence and will not promote a new model unless both training steps succeed. A failed classification run will not produce a broken promotion.

`notifier.py` is not in the main dependency chain. It is called by `registry.py` after a successful promotion — it does not run independently. `scheduler.py` similarly sits outside the chain; it owns the timing and calls `retrain.sh`, but has no knowledge of the model internals.

### The two main workflows

**Workflow 1 — User request (inference)**

```
User query
    ↓
NLP/LLM layer extracts structured fields
(line, station, hour, day_of_week, is_weekend, month, week, year)
    ↓
POST /predict to api.py
    ↓
predictor.py constructs feature vector
  → looks up route averages from route_stats.csv
  → infers delay code if not provided
  → runs Stage 1: classifier → delay_probability
  → if probability > threshold: runs Stage 2: regressor → duration estimate
    ↓
Returns structured dict
{delayed, delay_probability, confidence, predicted_duration_minutes,
 duration_range, code_used, code_was_inferred}
    ↓
NLP/LLM layer formats into natural language response
```

**Workflow 2 — Scheduled retraining**

```
scheduler.py wakes up at configured time (default: Sunday 2am)
    ↓
calls retrain.sh
    ↓
retrain.sh runs in sequence:
  1. python ph1_classification.py    → new classification artifacts
  2. python ph1_regression.py        → new regression artifacts
  3. python build_lookup.py          → updated route_stats.csv
  4. python registry.py promote-latest all
        ↓
        writes model_registry.json (new versions now active)
        sends SIGHUP to uvicorn process
            → uvicorn finishes in-flight requests, reloads predictor.py
               with new model artifacts (no dropped requests)
        POSTs to all webhook subscribers:
            → backend:      POST /ml-updated  {"changes": {...}}
            → NLP service:  POST /ml-updated  {"changes": {...}}
    ↓
retrain.sh logs everything to logs/retrain_YYYYMMDD_HHMMSS.log
Only promotes if both training steps succeeded
```

**Workflow 3 — Initial production launch**

This runs once, in order, before the service can accept requests:

```
1. python ph1_classification.py    # train classification model
2. python ph1_regression.py        # train regression model
3. python build_lookup.py          # build feature store
4. python registry.py promote-latest all   # register versions
5. uvicorn api:app --host 0.0.0.0 --port 8000   # start API
6. python scheduler.py             # start retraining scheduler
```

Steps 1–4 run once. Steps 5–6 run as persistent processes for the life of the deployment. The scheduler then takes over responsibility for running steps 1–4 on whatever schedule is configured.

---

## 1. Local Development Setup

### STEP 1.1 — Repository structure

The code assumes this structure exists in the repo:

```
ttc_information_chatbot/
├── data/
│   └── processing/
│       └── cleaned_ttc_delay_data.csv   ← training data
├── models/
│   ├── src/        ← all .py and .sh files go here
│   ├── trained/    ← generated artifacts (git-ignore this)
│   └── experiments/
└── logs/           ← created automatically on first retrain
```

> **WARNING** Add the following entries to `.gitignore` in the repo root. Do **not** use the broad `models/trained/` entry — it would also ignore the config files that should be committed:

```
# ML artifacts — large binary files, do not commit
models/trained/**/*.pkl
models/trained/*/metrics.json
models/trained/*/metrics_comparison.json
models/trained/*/feature_importance.json
models/trained/*/metadata.json

# Runtime files — generated at runtime, meaningless to commit
models/trained/ml_service.pid

# Logs
logs/

# Python cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Keep these — configuration files that should be in version control
# (the ! means "do not ignore this even though the parent folder matches")
!models/trained/webhook_subscribers.json
!models/trained/scheduler_config.json
!models/trained/model_registry.json
```

### STEP 1.2 — Install Python dependencies

Add the following to `requirements.txt` in the repo root (merge with anything already there). Keep `requirements.txt` in the repo root — that is the standard location and where deployment tools like Railway and Render look for it automatically:

```
lightgbm>=4.0.0
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.11.0
joblib>=1.3.0
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
```

> **WARNING** LightGBM and scikit-learn are the most version-sensitive packages here. A version mismatch between training and inference environments causes silent prediction errors. Always install from `requirements.txt` rather than ad-hoc.

### STEP 1.3 — Copy all files into models/src/

Copy `.py` files and `retrain.sh` into `models/src/`. The scripts use relative paths anchored at the repo root, so they must live in `models/src/` to resolve paths correctly.

```bash
# Verify paths resolve correctly
cd models/src && python -c "from ph1_classification import DEFAULT_DATA_PATH; print(DEFAULT_DATA_PATH)"
```

The filepath should point to `cleaned_ttc_delay_data.csv`. If it does not, check that the repo root matches the expected structure from Step 1.1.

> **NOTE — GitHub Codespaces** Codespaces does not persist the filesystem between sessions by default. Installed packages and trained model files may be gone when you reopen a Codespace. To handle this automatically, create `.devcontainer/devcontainer.json` in the repo root:
> ```json
> {
>     "name": "TTC ML",
>     "postCreateCommand": "pip install -r requirements.txt"
> }
> ```
> This tells Codespaces to reinstall dependencies automatically every time the environment starts. For trained models: either re-run training with `--no-tune` (takes a couple of minutes) or temporarily commit `models/trained/` to preserve them, then revert once you have a proper cloud deployment.

---

## 2. Initial Training Run

This phase runs once to produce the first set of trained model artifacts. After this, the scheduler handles retraining automatically.

### STEP 2.1 — Train the classification model

```bash
cd models/src
python ph1_classification.py
```

What this does: loads `cleaned_ttc_delay_data.csv`, performs an 80/20 chronological split, trains 5 models (2 baselines, Logistic Regression, Random Forest, LightGBM untuned + tuned), and saves artifacts to `models/trained/classification/v<timestamp>/`.

Expected runtime: 15–45 minutes depending on hardware (hyperparameter search runs 50 iterations × 5 CV folds). To run faster during development:

```bash
python ph1_classification.py --no-tune   # ~2 minutes, skips hyperparameter search
```

> **WARNING** Always use the tuned version for production. The `--no-tune` flag exists for development iteration only. Production results:
>
> | Model | F1 | Recall | AUC-ROC | AUC-PR |
> |-------|-----|--------|---------|--------|
> | lightgbm_tuned | 0.733 | **0.887** | 0.888 | 0.790 |
> | lightgbm_untuned | 0.727 | 0.732 | 0.892 | 0.806 |
> | logistic_regression | 0.709 | 0.686 | 0.886 | 0.787 |
> | random_forest | 0.703 | 0.896 | 0.849 | 0.720 |
>
> Recall is the critical metric for a commuter alert system — missing a real delay is worse than a false alarm. The tuned LightGBM achieves 0.887 recall. Note that tuning traded some AUC-PR (0.790 vs 0.806 untuned) in exchange for better recall — this is the correct trade-off for this use case since the optimisation target was F1.

Artifacts saved after this step:

- `lgbm_classifier.pkl` — the trained model
- `one_hot_encoder.pkl` — fitted encoder (required at inference)
- `feature_names.pkl` — ordered feature list
- `metrics.json` — full metrics for all 5 models including confusion matrix and AUC-PR
- `metrics_comparison.json` — side-by-side comparison table
- `feature_importance.json` — top features ranked by importance
- `metadata.json` — run config, best params, CV score

### STEP 2.2 — Train the regression model

```bash
python ph1_regression.py
```

What this does: same pipeline structure as classification but predicts delay duration in minutes. Trains on delayed rows only (`min_delay_capped > 0`). The encoder is fitted on all rows to avoid unknown-category errors at inference.

Expected runtime: similar to classification. Same `--no-tune` flag available.

> **NOTE** The regression model's R² is 0.183 because delay duration is inherently noisy — a 2-minute and a 45-minute delay can have identical input features, and weather, cascading effects, and crew response time all add variance that historical route data cannot capture. What matters is that the tuned LightGBM beats both baselines on RMSE (6.41 vs 7.12 for mean baseline, 7.34 for median baseline), getting within 6.4 minutes on average vs the baseline's 7.1. The `duration_range` field (±35%) in the API response communicates this uncertainty clearly to users.
>
> | Model | MAE | RMSE | R² |
> |-------|-----|------|-----|
> | lightgbm_tuned | 3.809 | 6.413 | **0.183** |
> | lightgbm_untuned | 3.874 | 6.507 | 0.159 |
> | baseline_mean | 4.355 | 7.120 | -0.007 |
> | baseline_median | 3.396 | 7.337 | -0.069 |

### STEP 2.3 — Build the feature lookup table

```bash
python build_lookup.py
```

What this does: computes historical average delay statistics (`route_avg_delay`, `route_hour_avg_delay`, `route_day_hour_avg_delay`) from the training split only, and saves them to `data/processing/route_stats.csv`.

This file is critical for inference. Without it, the predictor cannot construct the feature vector from a user query. It must be rebuilt every time the models are retrained.

> **NOTE** The lookup table is computed from the training split only (first 80% of data by date). Using test data here would be leakage. This matches the boundary used in the training pipelines.

### STEP 2.4 — Register the trained versions

```bash
python registry.py promote-latest all
```

What this does: reads the artifact directories, identifies the newest version of each model type, writes `model_registry.json` marking them as active, and (once the service is running) triggers a graceful restart and sends webhook notifications.

Check what was registered:

```bash
python registry.py status
```

---

## 3. Running the Service Locally

### STEP 3.1 — Start the ML API

```bash
cd models/src
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag restarts the server automatically when code changes. Remove it in production.

On startup the service:

- Writes its PID to `models/trained/ml_service.pid` (used by `notifier.py` for graceful restarts)
- Loads both trained models into memory
- Loads the route lookup table

Verify it is running:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{ "status": "ok", "clf_version": "v20260301_...", "reg_version": "v20260301_...", "lookup_loaded": true }
```

Interactive API docs: `http://localhost:8000/docs`

> **TIP** The API can be tested directly from `/docs` without writing any code.

### STEP 3.2 — Test a prediction

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"line":"Line 1","station":"BLOOR STATION","hour":17,
       "day_of_week":3,"is_weekend":0,"month":3,"week":10,"year":2026}'
```

The `code` field is intentionally omitted here — the predictor will infer the most common code for Line 1 automatically. Expected response:

```json
{
  "delayed": true,
  "delay_probability": 0.62,
  "confidence": "medium",
  "predicted_duration_minutes": 5.8,
  "duration_range": [3.8, 7.8],
  "code_used": "SUDP",
  "code_was_inferred": true
}
```

What each field means:

- `delayed` — whether the model predicts a delay will occur (based on threshold, default 0.5)
- `delay_probability` — raw probability from the classifier (0–1)
- `confidence` — `high` / `medium` / `low` based on how far the probability is from the threshold and how well the route is represented in training data
- `predicted_duration_minutes` — regression estimate; only meaningful when `delayed` is true
- `duration_range` — ±35% band around the duration estimate; communicates that this is a rough estimate not a precise prediction
- `code_used` — the delay code the predictor used to construct features
- `code_was_inferred` — `true` means the caller did not supply a code and the predictor inferred the most common one for this line; the NLP layer should be aware of this field

### STEP 3.3 — Start the scheduler (background process)

```bash
# Set the schedule first
python scheduler.py --set-schedule weekly --day sunday --hour 2

# Start the scheduler as a background process
python scheduler.py &

# Verify status
python scheduler.py --status
```

The scheduler runs a lightweight poll every 60 seconds, consuming negligible CPU. It wakes up at the configured day and time, runs `retrain.sh`, and goes back to sleep.

The `--set-schedule` command writes your chosen schedule to `models/trained/scheduler_config.json`. This file is what the scheduler reads on startup — if it does not exist, the scheduler defaults to `on_demand` mode and will not retrain automatically. The file should be committed to version control (it is included in the `.gitignore` exceptions from Step 1.1) so the schedule survives a redeploy.

> **TIP** During development, use `on_demand` mode so retraining doesn't run unexpectedly: `python scheduler.py --set-schedule on_demand`. Switch to `weekly` before deploying.

---

## 4. Teammate Integration

### STEP 4.1 — Register teammate webhook endpoints

`webhook_subscribers.json` does not exist until you create it. There are two ways to create it:

**Option A — using the notifier CLI (recommended)**

Once your colleagues know their local URLs, run this in Codespaces:

```bash
python notifier.py --register backend http://localhost:3000/ml-updated
python notifier.py --register nlp_service http://localhost:5000/ml-updated
```

This creates `models/trained/webhook_subscribers.json` automatically with the correct structure.

**Option B — create it manually as a placeholder**

If you want the file committed to the repo before your colleagues have URLs, create `models/trained/webhook_subscribers.json` with this content:

```json
{
    "subscribers": [
        {
            "name": "backend",
            "url": "http://localhost:3000/ml-updated",
            "enabled": false
        },
        {
            "name": "nlp_service",
            "url": "http://localhost:5000/ml-updated",
            "enabled": false
        }
    ]
}
```

The `"enabled": false` flag means notifications are registered but will not fire until you flip them to `true`. This is safe — your colleagues' endpoints do not exist yet during development.

Edit this file directly to update URLs or enable/disable a subscriber as teammates come online.

Test that notifications are being delivered without triggering a real restart:

```bash
python notifier.py --dry-run
```

> **NOTE** `/ml-updated` endpoints just need to accept a POST and return `200 OK`. The backend determines what to do with the payload (flush a cache, update a version badge in the UI, log it). A failed notification never blocks a promotion — the ML service restarts regardless.

### STEP 4.2 — Share the interface spec with the NLP and backend colleagues

Hand over `ml_interface_spec.docx` from `docs/`. The sections most relevant to the NLP layer:

- Section 4 — the `code` field is optional and why (should be omitted in most cases)
- Section 7 — confidence level language guide (critical for prompt design)
- Section 8 — when to use the batch endpoint for comparative queries
- Section 9 — responsibility boundary: what the NLP layer owns vs what the ML layer owns

The backend colleague does not need a separate spec document — the FastAPI auto-generated docs at `http://localhost:8000/docs` provide a full interactive Swagger UI with every endpoint, field type, description, and example value. The only thing to tell the backend colleague up front is the service URL (dev: `http://localhost:8000`, prod: TBD once deployment platform is decided).

### STEP 4.3 — Team alignment before integration

Before the NLP and backend colleagues begin integrating against the ML layer, a set of decisions need to be made together. These are documented in full in **Section 9 — Open Decisions** at the end of this guide, including who needs to be involved in each decision and what the default is if no explicit decision is made.

The most time-sensitive items are deployment platform (blocks the backend from integrating), station name normalisation ownership (blocks the NLP layer from building entity extraction), and the predictive vs live status distinction (must be agreed before any user-facing copy is written).

---

## 5. Cloud Deployment

The deployment steps below apply to any cloud platform that runs persistent processes. Specific platform setup (Railway, Render, AWS, GCP) will vary in the dashboard UI but the underlying commands are the same.

### STEP 5.1 — Environment variables to configure

Set these in the cloud platform's environment config (do not hardcode):

- **`TTC_CLF_VERSION`** Optional — pin a specific classification artifact version. Omit to use latest active.
- **`TTC_REG_VERSION`** Optional — pin a specific regression artifact version. Omit to use latest active.
- **`TTC_LOOKUP_PATH`** Optional — override path to `route_stats.csv` if not at default location.
- **`TTC_DELAY_THRESHOLD`** Optional — default 0.5. Set to 0.40 for higher recall on commuter alerts.
- **`TTC_WEBHOOK_SECRET`** Optional but recommended — HMAC secret for signing webhook payloads. Set the same value on all subscriber services to verify authenticity.

### STEP 5.2 — Two processes to run

The cloud deployment runs exactly two persistent processes:

```bash
# Process 1 — ML API
uvicorn models/src/api:app --host 0.0.0.0 --port 8000 --workers 2

# Process 2 — Retraining scheduler
python models/src/scheduler.py
```

Most platforms allow multiple processes to be defined in a Procfile:

```
web:       uvicorn models/src/api:app --host 0.0.0.0 --port $PORT --workers 2
scheduler: python models/src/scheduler.py
```

> **WARNING** Use `--workers 2` (not more) on free/low-cost cloud tiers. LightGBM models are large in memory — too many workers will exhaust the instance's RAM.

### STEP 5.3 — First deployment sequence

On a fresh cloud instance, run these in order before starting the services:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run initial training (do this once — scheduler handles future retrains)
bash models/src/retrain.sh

# 3. Verify artifacts exist
python models/src/registry.py status

# 4. Register teammate webhooks (use production URLs)
python models/src/notifier.py --register backend https://your-backend.com/ml-updated
python models/src/notifier.py --register nlp https://your-nlp-service.com/ml-updated

# 5. Start both processes
uvicorn models/src/api:app --host 0.0.0.0 --port 8000 &
python models/src/scheduler.py &
```

### STEP 5.4 — Verify deployment health

```bash
# Health check
curl https://your-ml-service.com/health

# Check scheduler status
curl https://your-ml-service.com/scheduler-status

# Test a live prediction
curl -X POST https://your-ml-service.com/predict \
  -H "Content-Type: application/json" \
  -d '{"line":"Line 1","station":"BLOOR STATION","hour":17,
       "day_of_week":3,"is_weekend":0,"month":3,"week":10,"year":2026}'
```

---

## 6. Automatic Retraining — Operations & Troubleshooting

The full retraining flow is documented in Section 0.1 Workflow 2. This section covers what to do when things go wrong, how to verify a retrain succeeded, and how to roll back to a previous model version.

### STEP 6.1 — Trigger a manual retrain

To retrain outside the schedule (e.g. after new data arrives, or to test the pipeline):

```bash
# Via the scheduler (recommended — uses the same path as automatic retraining)
python models/src/scheduler.py --run-now

# Or run retrain.sh directly
bash models/src/retrain.sh
```

### STEP 6.2 — Verify a retrain succeeded

After a retrain completes, check three things:

```bash
# 1. Check the scheduler recorded a successful run
python models/src/scheduler.py --status

# 2. Check which versions are now active
python models/src/registry.py status

# 3. Check the API loaded the new versions
curl http://localhost:8000/health
```

The health endpoint response will show the active version strings:

```json
{ "status": "ok", "clf_version": "v20260307_055529", "reg_version": "v20260307_065006", "lookup_loaded": true }
```

If the version strings match what `registry.py status` reports, the new models are live.

### STEP 6.3 — Read the retrain log

Every retrain run writes a timestamped log to `logs/`:

```bash
# View the most recent log
cat logs/retrain_latest.log

# Or view a specific run by timestamp
ls logs/
cat logs/retrain_YYYYMMDD_HHMMSS.log
```

A successful log ends with lines like:

```
[INFO] Classification training complete
[INFO] Regression training complete
[INFO] Lookup table rebuilt: 33925 rows
[INFO] Promoted classification v20260307_055529
[INFO] Promoted regression v20260307_065006
[INFO] SIGHUP sent to uvicorn PID 12345
[INFO] Webhook delivered: backend
[INFO] Webhook delivered: nlp_service
[INFO] Retrain complete
```

A failed run will show which step failed and will **not** include a promotion line — meaning the previous model version stays active. The service is never left in a broken state by a failed retrain.

### STEP 6.4 — Roll back to a previous model version

If a retrain produces a model that behaves worse (lower recall on a spot-check, unexpected prediction changes), roll back by pinning the previous version:

**Option A — pin via environment variable (recommended for production)**

Set these in the cloud platform's environment config and redeploy:

```bash
TTC_CLF_VERSION=v20260228_112233   # previous known-good version
TTC_REG_VERSION=v20260228_115500
```

The service will load these specific artifact versions on next startup instead of whatever `registry.py` has marked as active.

**Option B — promote the previous version directly**

```bash
# List available versions
python models/src/registry.py status

# Promote a specific older version
python models/src/registry.py promote classification v20260228_112233
python models/src/registry.py promote regression v20260228_115500
```

This updates `model_registry.json`, triggers a graceful service reload via SIGHUP, and sends webhook notifications to teammates — the same sequence as a normal promotion.

> **NOTE** Old artifact versions are kept in `models/trained/` until you manually delete them. Do not delete old versions until you are confident the new one is performing correctly. On free-tier cloud platforms with limited disk, keep at least the two most recent versions.

### STEP 6.5 — What to do if the service does not reload after promotion

If the service fails to pick up new models after a promotion (the `/health` endpoint still shows the old version strings), the SIGHUP may not have reached the process:

```bash
# Check if the PID file is current
cat models/trained/ml_service.pid

# Confirm that PID is actually running
ps aux | grep uvicorn

# If the PID is stale, restart manually
pkill -f uvicorn
uvicorn models/src/api:app --host 0.0.0.0 --port 8000 --workers 2
```

The service writes a fresh PID file on every startup. A stale PID file means the service was restarted outside the normal flow (e.g. a platform restart) without the notifier being aware of the new PID. After a manual restart, the service will reload the currently active versions from `model_registry.json` automatically.

---

## 7. What Changes When You Pick a Platform

The code is platform-agnostic. The only things that change per platform are:

- **Production URL:** replace `localhost:8000` with the deployed URL in webhook registrations and teammate documentation.
- **How to start the two processes:** some platforms use a Procfile, others have a dashboard UI, others use Docker. The commands themselves don't change.
- **Persistent storage:** some free-tier platforms reset the filesystem on redeploy (Render free tier does this). If so, trained artifacts need to be stored in cloud storage (S3, GCS) and downloaded on startup. This is the main deployment complexity to watch for.
- **Port:** some platforms set the `PORT` environment variable dynamically. Replace `--port 8000` with `--port $PORT` if required.

> **ACTION** Filesystem persistence is the most common free-tier deployment issue. Confirm whether the filesystem is persistent between deploys before committing to a platform. Railway and Render paid tiers have persistent disks. Free tiers on Render do not.

---

## 8. Quick Reference — Common Commands

### Development

```bash
python ph1_classification.py --no-tune   # fast training, skips hyperparameter search
python ph1_regression.py --no-tune
python build_lookup.py
python registry.py status                # show active versions
python registry.py promote-latest all   # promote newest artifacts for both models
uvicorn api:app --reload --port 8000
python scheduler.py --set-schedule on_demand   # disable auto-retraining during dev
```

### Production

```bash
bash retrain.sh                           # full retrain + promote + notify
python scheduler.py --run-now             # manual retrain trigger
python scheduler.py --status              # check last/next run
python notifier.py --dry-run              # test webhooks without restarting
curl http://localhost:8000/health
curl http://localhost:8000/scheduler-status
```

### Model version management

```bash
python registry.py status                              # list all versions and which are active
python registry.py promote-latest all                  # promote newest of both models
python registry.py promote classification v20260228_112233   # pin a specific version
python registry.py promote regression v20260228_115500
```

### Troubleshooting

```bash
cat logs/retrain_latest.log              # last retrain log
python registry.py status                # which versions are active
python notifier.py --dry-run             # verify webhook targets are reachable
cat models/trained/ml_service.pid        # confirm service PID

# Check a .py or .sh file for invisible characters before running
# (files copied from a browser or chat may contain U+00A0 non-breaking spaces)
grep -P "\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f" filename.py
# Returns nothing if clean; returns affected lines if not
```

> **WARNING** If the service fails to restart after a promotion (SIGHUP not received), the PID file may be stale. Delete `models/trained/ml_service.pid` and restart uvicorn manually. It will write a fresh PID file on startup. See Section 6.5 for the full procedure.

---

## 9. Open Decisions — Team Alignment Required

The following items require a conversation and decision between team members before the system goes live. Each item lists who needs to be involved and what the default is if no decision is made.

### With the NLP / LLM Colleague

**1. Station name normalisation**
Who is responsible for converting what a user says ("Spadina", "Spadina station", "the Spadina stop") into the exact uppercase format the model expects ("SPADINA STATION")? Recommended: NLP layer owns this since it is already doing entity extraction. The full valid station name list is in `data/processing/route_stats.csv`, Station column. *Default if no decision: NLP layer normalises to uppercase and appends STATION.*

**2. Ambiguous station names**
"Bloor" could mean Bloor-Yonge or Bloor-Christie. Does the NLP layer ask the user to clarify before calling the ML API, or call the API with its best guess and caveat the response? Agree on one pattern and apply it consistently. *Default if no decision: ask the user to clarify before calling the API.*

**3. Delay threshold**
The ML spec says 0.5 but recommends 0.40 for a commuter-facing chatbot. This is a product decision: what is the acceptable trade-off between false alarms and missed delays? Missing a real delay is worse than a false alarm for most commuters. *Default if no decision: 0.50 until go-live, then reassess.*

**4. Low confidence response language**
The ML interface spec gives suggested language for low confidence predictions but the NLP colleague may want to handle it differently. Align on this before go-live so the chatbot feels consistent. *Default if no decision: use the language in ML interface spec Section 8.*

**5. Fallback when ML service is down**
The spec says "direct the user to TTC service alerts." Agree on exactly what that looks like in the chatbot response and what URL or resource to point users to. *Default if no decision: "I'm unable to check delay predictions right now. Please check ttc.ca or the TTC app for current service status."*

### With the Backend Colleague

**6. Deployment platform**
Where is this actually running? This determines the production URL, whether the ML service and backend are on the same server or separate, and how the backend calls the ML API. Options are covered in Section 7 of this guide. *No default — this decision must be made before production deployment.*

**7. Same service or separate service**
The ML layer can be called as a direct Python import (if everything runs in one process) or as a separate REST service over HTTP. Simpler to start with direct import; easier to scale independently as separate services. *Default if no decision: start with direct Python import and migrate to REST if scaling needs arise.*

**8. API authentication**
Currently `api.py` has no authentication. If the API is publicly reachable even temporarily, anyone can call it. If the backend is the only caller and they are on the same server, authentication can be skipped. If the API is exposed to the network, add a simple header API key. *Default if no decision: no authentication for internal-only development; add before any public exposure.*

**9. How the backend passes time context**
The ML API currently takes `hour`, `day_of_week`, `is_weekend`, `month`, `week`, and `year` as separate fields. The alternative is to accept a single ISO timestamp and have the ML layer compute those fields itself. *Default if no decision: keep separate fields and have the NLP or backend layer compute them from the user's local time.*

**10. Deployment timing**
The ML service needs to be running before the backend can integrate against it. Agree on when a stable development instance will be available so the backend colleague is not blocked. The ML layer is ready now in Codespaces on `ml_branch`.

### All Three Team Members

**11. Retraining schedule**
How often do the models retrain — weekly, monthly, on demand? When a new model is promoted via `registry.py`, the service reloads automatically via SIGHUP and notifies the backend and NLP layer via webhook. Who owns the retraining process and who is responsible for verifying the new model before it goes live? *Default if no decision: weekly retraining on Sunday at 2am as configured in `scheduler_config.json`, with `--no-tune` flag until the team agrees to enable full tuning.*

**12. What the chatbot is actually answering — MOST IMPORTANT**

The ML model predicts delays based on historical patterns. It does not know about live TTC service disruptions happening right now. The entire team must be aligned that this chatbot is a **predictive tool** ("Line 1 tends to have delays at this time of day on Thursdays") — not a **live status tool** ("Line 1 is currently delayed"). This distinction must be reflected in the NLP layer's prompts, the backend's UI copy, and any user-facing descriptions of the chatbot. If users believe they are getting live status and they are not, trust will be broken the first time a predicted delay does not materialise or a real delay is missed. *There is no default — this must be explicitly agreed and communicated before go-live.*
