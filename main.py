"""
TTC Chatbot - Application Entry Point
======================================
Repo path: main.py (repo root)

This is the single entry point for the entire TTC chatbot application.
It wires together all three layers and starts the web server.

    Frontend (browser)
        |  HTTP
        v
    main.py  <-- YOU ARE HERE
        |  Python import
        v
    nlp/handler.py  <-- NLP teammate builds this
        |  Python import
        v
    models/src/predictor.py  <-- ML layer (built, working)

HOW TO RUN
----------
    # Development
    python main.py

    # Or with uvicorn directly (recommended)
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

    # Production - 4 workers handles ~100 concurrent users comfortably
    uvicorn main:app --host 0.0.0.0 --port $PORT --workers 4

ENVIRONMENT VARIABLES
---------------------
    PORT            Web server port (default: 8000)
    DEBUG           Set to "true" for verbose logging (default: false)
    ML_THRESHOLD    Delay prediction threshold 0.0-1.0 (default: 0.5)

NLP TEAMMATE - READ THIS
------------------------
Your entry point is nlp/handler.py. You must implement one function:

    def handle_message(user_message: str, session_id: str, context: dict) -> dict

If you are calling an external LLM API (OpenAI, Anthropic etc.), implement
it as async for better performance under load:

    async def handle_message(user_message: str, session_id: str, context: dict) -> dict

See nlp/handler.py for the full contract and stub implementation.
The ML predictor is already initialised at startup - import it via:

    from models.src.predictor import get_predictor
    predictor = get_predictor()   # returns the already-loaded singleton

BACKEND TEAMMATE - READ THIS
-----------------------------
The web framework is FastAPI. Add your routes, middleware, database
connections, and auth logic in backend/. The core chat endpoint is
defined here in main.py. Do not move it - other layers depend on it.
Register your routes by importing them here:

    from backend.routes import router as backend_router
    app.include_router(backend_router)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Path setup - must come before internal imports
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models" / "src"))


def load_local_env(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from a local .env file if present."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_local_env(ROOT / ".env")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Web framework
# ---------------------------------------------------------------------------
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

# ---------------------------------------------------------------------------
# Internal layers
# ---------------------------------------------------------------------------
# ML layer - already built and working
from models.src.predictor import get_predictor, DelayPredictor

# NLP layer - stub until NLP teammate implements nlp/handler.py
try:
    from nlp.handler import handle_message
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False

# Database layer
from backend.database import get_db, init_db
from backend.services import SessionService, MessageService

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORT = int(os.getenv("PORT", "8000"))
ML_THRESHOLD = float(os.getenv("ML_THRESHOLD", "0.5"))


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TTC Delay Prediction Chatbot",
    description="Predicts TTC subway delays based on historical patterns.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - update origins before production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO: restrict to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React frontend from dist folder
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    # Mount static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

# Include backend routes (session/message management, database endpoints)
from backend.routes import router as backend_router
from backend.auth_routes import router as auth_router
app.include_router(backend_router)
app.include_router(auth_router)

# ---------------------------------------------------------------------------
# Startup - load ML models once
# ---------------------------------------------------------------------------
_predictor: Optional[DelayPredictor] = None


@app.on_event("startup")
async def startup():
    global _predictor
    log.info("Starting TTC Chatbot...")

    # Initialize database
    log.info("Initializing database...")
    try:
        init_db()
        log.info("Database initialized successfully.")
    except Exception as e:
        log.error(f"Failed to initialize database: {e}")

    # Set up default users
    log.info("Setting up default users...")
    try:
        from backend.auth import setup_default_users
        db = next(get_db())
        setup_default_users(db)
        log.info("Default users configured (admin/demo/moderator).")
    except Exception as e:
        log.warning(f"Could not set up default users: {e}")

    # Load ML models
    log.info("Loading ML models...")
    try:
        _predictor = get_predictor()
        log.info("ML models loaded successfully.")
    except Exception as e:
        log.error(f"Failed to load ML models: {e}")
        log.error("Run the training pipeline first: see README.md Step 2")
        # Don't crash - health endpoint will report degraded status

    if NLP_AVAILABLE:
        log.info("NLP handler loaded successfully.")
    else:
        log.warning(
            "NLP handler not found at nlp/handler.py. "
            "Chat endpoint will return a placeholder response. "
            "NLP teammate: implement nlp/handler.py to enable full functionality."
        )

    log.info(f"Application ready. Docs at http://localhost:{PORT}/docs")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single message from the user to the chatbot."""
    message: str
    session_id: str = "default"
    # Optional: frontend can pass context from previous turns
    context: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """The chatbot's response to the user."""
    response: str
    session_id: str
    # Optional: structured data the frontend can use to enhance the UI
    # e.g. show a delay badge, highlight a line on a map
    data: Optional[Dict[str, Any]] = None
    # Whether the ML predictor was involved in this response
    ml_used: bool = False


class DirectPredictRequest(BaseModel):
    """
    Direct ML prediction request - bypasses NLP layer.
    For backend/testing use. Frontend should use /chat instead.
    """
    line: str
    station: str
    hour: int
    day_of_week: int
    is_weekend: int
    month: int
    week: int
    year: int
    code: Optional[str] = None
    threshold: float = ML_THRESHOLD


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=FileResponse)
async def root():
    """
    Serves the React frontend (built with Vite).
    """
    frontend_index = ROOT / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        return frontend_index
    else:
        return FileResponse(
            path=ROOT / "frontend" / "dist" / "index.html",
            status_code=200,
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessage, db: DBSession = Depends(get_db)):
    """
    Main chat endpoint. All user messages come through here.

    Flow:
        1. Receive user message
        2. Get or create session in database
        3. Save user message to database
        4. Pass to NLP handler (extracts intent + entities + calls ML if needed)
        5. Save bot response to database
        6. Return natural language response
    """
    log.info(f"[{request.session_id}] User: {request.message}")

    # Get or create session in database
    session = SessionService.get_or_create_session(request.session_id, db)
    session_id = session.id

    # Save user message to database
    try:
        user_msg_obj = MessageService.add_user_message(
            session_id=session_id,
            content=request.message,
            db=db,
        )
    except Exception as e:
        log.error(f"Failed to save user message: {e}")

    # Prepare session context for NLP handler
    session_context = SessionService.get_session_context(session_id, db)

    if NLP_AVAILABLE:
        try:
            # Use asyncio.to_thread so a sync handle_message does not block
            # other requests. If handle_message is already async, call it
            # directly with: result = await handle_message(...)
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    handle_message,
                    user_message=request.message,
                    session_id=session_id,
                    context=session_context,
                ),
                timeout=10.0,  # seconds - prevents slow LLM calls blocking workers
            )

            response_text = result.get("response", "Sorry, I could not process that.")
            ml_used = result.get("ml_used", False)
            ml_model_version = result.get("ml_model_version")
            prediction_data = result.get("data")

            log.info(f"[{session_id}] Bot: {response_text[:80]}")

            # Save bot message to database
            try:
                bot_msg_obj = MessageService.add_bot_message(
                    session_id=session_id,
                    content=response_text,
                    db=db,
                    ml_used=ml_used,
                    ml_model_version=ml_model_version,
                    prediction_data=prediction_data,
                )
            except Exception as e:
                log.error(f"Failed to save bot message: {e}")

            return ChatResponse(
                response=response_text,
                session_id=session_id,
                data=prediction_data,
                ml_used=ml_used,
            )
        except asyncio.TimeoutError:
            log.error(f"[{session_id}] NLP handler timed out after 10 seconds")
            raise HTTPException(
                status_code=504,
                detail="Response took too long. Please try again."
            )
        except Exception as e:
            log.error(f"NLP handler error: {e}")
            raise HTTPException(status_code=500, detail="Chat processing failed.")

    else:
        # NLP layer not yet implemented - return placeholder
        error_response = (
            "NLP layer not yet available. "
            "The ML prediction service is running - "
            "check /docs to test predictions directly."
        )

        # Save placeholder bot message
        try:
            bot_msg_obj = MessageService.add_bot_message(
                session_id=session_id,
                content=error_response,
                db=db,
                ml_used=False,
            )
        except Exception as e:
            log.error(f"Failed to save bot message: {e}")

        return ChatResponse(
            response=error_response,
            session_id=session_id,
            ml_used=False,
        )


@app.post("/predict")
async def predict(request: DirectPredictRequest):
    """
    Direct ML prediction endpoint - bypasses NLP layer.
    Use this for:
    - Backend integration testing
    - When the backend computes structured inputs itself
    - Batch processing outside of chat context

    For the chat interface, use /chat instead.
    """
    if _predictor is None:
        raise HTTPException(
            status_code=503,
            detail="ML models not loaded. Run training pipeline first."
        )
    try:
        result = _predictor.predict(
            line=request.line,
            station=request.station,
            hour=request.hour,
            day_of_week=request.day_of_week,
            is_weekend=request.is_weekend,
            month=request.month,
            week=request.week,
            year=request.year,
            code=request.code,
            threshold=request.threshold,
        )
        return JSONResponse(content=result)
    except Exception as e:
        log.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/health")
async def health():
    """
    Health check endpoint. Covers all layers.
    Call this before making predictions to verify the service is ready.
    """
    ml_status = "ok" if _predictor is not None else "not_loaded"
    nlp_status = "ok" if NLP_AVAILABLE else "not_implemented"

    try:
        ml_detail = _predictor.health() if _predictor else {}
    except Exception:
        ml_detail = {}
        ml_status = "error"

    overall = "ok" if ml_status == "ok" else "degraded"

    return {
        "status": overall,
        "ml_layer": {"status": ml_status, **ml_detail},
        "nlp_layer": {"status": nlp_status},
        "version": "1.0.0",
    }


@app.get("/{full_path:path}", response_class=FileResponse)
async def spa_fallback(full_path: str):
    """
    Catch-all route for SPA (Single Page Application).
    Serves index.html for any route not matched by API endpoints.
    This allows React Router to handle client-side navigation.
    """
    frontend_index = ROOT / "frontend" / "dist" / "index.html"
    if frontend_index.exists():
        return frontend_index
    else:
        raise HTTPException(status_code=404, detail="Frontend not built. Run: cd frontend && npm run build")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    workers = 1 if DEBUG else 4  # 1 worker in dev (supports --reload), 4 in production
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=DEBUG,
        workers=workers if not DEBUG else None,
        log_level="debug" if DEBUG else "info",
    )
