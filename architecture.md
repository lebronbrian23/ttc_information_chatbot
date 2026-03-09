# TTC Delay Prediction Chatbot — System Architecture

> **Read this first.** One page overview for the whole team.
> Version 1.0 | March 2026 | Architect: ML Engineer

---

## 1. What Is This System

A chatbot that predicts TTC subway delays based on historical patterns. A user types a natural language question. The system extracts the relevant route and time, runs a machine learning prediction, and returns a plain English answer.

> **Important:** This is a **PREDICTIVE** system, not a live status feed. It answers questions like *"Line 1 tends to be delayed at this time on Thursdays"* — not *"Line 1 is currently delayed."* The whole team must reflect this in every user-facing message.

---

## 2. How It Works — Request Flow

```
User types:  "Will Line 1 be delayed at Bloor around 5pm Thursday?"
                              |
                              v
         Frontend  (browser / mobile app)
                              |   HTTP POST /chat
                              v
         main.py  <── APPLICATION ENTRY POINT
                              |   Python import
                              v
         nlp/handler.py  <── NLP LAYER
             1. detect intent  (is this a delay query?)
             2. extract entities  (Line 1, Bloor, 17:00, Thursday)
             3. call ML predictor
             4. format response
                              |   Python import
                              v
         models/src/predictor.py  <── ML LAYER  (built, working)
             Stage 1: is a delay likely?  (classification)
             Stage 2: how long?           (regression)
                              |
                              v
         Response: "There is a 63% chance of delays on Line 1 at
          Bloor around 5pm Thursday. If delayed, expect 5–9 minutes."
```

---

## 3. Who Owns What

### ML Engineer — COMPLETE

| File | Purpose |
|---|---|
| `models/src/predictor.py` | Inference engine — call `get_predictor()` to use it |
| `models/src/api.py` | FastAPI REST wrapper (for direct ML access) |
| `models/src/ph1_classification.py` | Classification training pipeline |
| `models/src/ph1_regression.py` | Regression training pipeline |
| `models/src/build_lookup.py` | Builds `route_stats.csv` |
| `models/src/registry.py` | Manages active model versions |
| `models/src/scheduler.py` | Automatic weekly retraining |
| `models/src/notifier.py` | Webhooks on model promotion |
| `main.py` | Application entry point (architecture scaffold-Backend teammate will add and take forward) |
| `nlp/handler.py` | NLP layer stub (for NLP teammate to develop code and implement) |

---

### NLP / LLM Engineer & Data — TODO

| Responsibility | Details |
|---|---|
| `nlp/handler.py` | **YOUR MAIN FILE.** Implement `handle_message()` |
| `nlp/` | All your NLP code lives here |
| `data-pipeline/` | Data ingestion, cleaning, and pipeline ownership |
| Intent detection | Is this a delay query, general question, greeting? |
| Entity extraction | Pull line, station, time from natural language |
| ML integration | Call `get_predictor().predict()` with extracted entities |
| Response formatting | Turn ML result dict into natural language answer |
| Multi-turn context | Remember line/station between conversation turns |

---

### Backend / Frontend Engineer — TODO

| Responsibility | Details |
|---|---|
| `frontend/` | All UI code lives here (React, plain HTML, mobile) |
| `backend/` | Routes, auth, database, middleware |
| `POST /chat` | Already defined in `main.py` — do not move it |
| Register your routes | Import your router in `main.py` (see instructions there) |
| Replace `GET /` | `main.py` serves a dev UI at `/` — replace with real frontend |
| Session management | Generate and persist `session_id` per user conversation |
| Register webhook URL | Add your `/ml-updated` URL to `webhook_subscribers.json` |

---

## 4. Key Files — Where to Start

| File | What it is |
|---|---|
| `main.py` | Start here. The app entry point. Read the docstring before anything else. |
| `nlp/handler.py` | NLP teammate's file. Full contract in the docstring. |
| `models/src/predictor.py` | The ML engine. Call `get_predictor().predict()` to get a prediction. |
| /docs/ml_interface_spec.md | Full input/output contract for the ML layer. For NLP & Backend Engineers to read before integrating. |
| /docs/ml_pipeline_guide.md | How to run the training pipeline and deploy the service. |
| `data/processing/route_stats.csv` | Valid station names are in the `Station` column of this file. |

---

## 5. How to Run the System

### Step 1 — Train the models (once, then scheduler handles it)

```bash
cd /workspaces/ttc_information_chatbot/models/src
python ph1_classification.py --no-tune   # ~2 min dev — remove --no-tune for production
python ph1_regression.py --no-tune
python build_lookup.py
python registry.py promote-latest all
```

### Step 2 — Start the application

```bash
cd /workspaces/ttc_information_chatbot
python main.py                                                    # development
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4          # production
```

### Step 3 — Verify everything is running

```
GET  /health   <── check ML + NLP layer status
GET  /docs     <── interactive API testing (share with teammates)
GET  /         <── minimal dev chat UI
```

### Step 4 — NLP and Backend teammates: build into the running app

The app starts and serves responses immediately even without the NLP layer implemented. The ML layer is already fully working. Each teammate builds their layer independently and the system gets smarter as each piece is added.

---

## 6. Decisions Still Needed — Team Must Agree

| Decision | Default if not decided |
|---|---|
| Frontend technology (React vs plain HTML vs mobile) | Dev UI in `main.py` serves as placeholder |
| Backend technology (Flask vs FastAPI vs Node) | FastAPI already set up in `main.py` |
| Same process vs separate services | Same process — simplest for Phase 1 |
| Deployment platform (Railway, Render, AWS, GCP) | Codespaces for development |
| Delay threshold (0.5 vs 0.40 recommended) | 0.5 until team agrees |
| API authentication (none vs API key) | None for internal dev — add before public exposure |
| Retraining schedule (weekly vs monthly) | Weekly Sunday 2am — see `scheduler_config.json` |

> Full details on each decision are in **Section 8 of the ML Pipeline Guide**.

---

## 7. Team Contacts

| Role | Responsible for |
|---|---|
| ML Engineer (Architect) | ML layer, `main.py` scaffold, this document, system design |
| NLP / LLM Engineer & Data | `nlp/handler.py`, intent detection, entity extraction, response generation, data pipeline |
| Backend / Frontend Engineer | `frontend/`, `backend/`, UI, auth, database, session management |

---

*Questions? Start with the docstrings in `main.py` and `nlp/handler.py`, then refer to `docs/ml_interface_spec` — everything you need to know is there.*
