"""
TTC Chatbot - NLP Handler
==========================
Repo path: nlp/handler.py

THIS FILE IS THE NLP ENTRY POINT - 
=============================================
Implement the handle_message() function below.
Everything else in the system is already built and working.

OBJECTIVES
--------
1. Receive a raw user message e.g. "Will Line 1 be delayed at Bloor at 5pm?"
2. Detect the intent (delay query, general question, out of scope, etc.)
3. Extract entities (line, station, time) from the message
4. If it is a delay query - call the ML predictor with the extracted entities
5. Format the ML result into a natural language response
6. Return a dict with the response and any structured data

THE ML PREDICTOR - HOW TO USE IT
---------------------------------
The predictor is already loaded at startup. Import and use it like this:

    from models.src.predictor import get_predictor

    predictor = get_predictor()   # returns the already-loaded singleton - fast

    result = predictor.predict(
        line        = "Line 1",
        station     = "BLOOR STATION",    # must be uppercase - see Section 6 of spec
        hour        = 17,                 # 0-23
        day_of_week = 3,                  # 0=Monday, 6=Sunday
        is_weekend  = 0,                  # 1 if Sat/Sun
        month       = 3,
        week        = 10,
        year        = 2026,
        # code is optional - omit it and ML infers the most common code for the line
    )

    # result is a plain dict - see THE PREDICTION RESULT section below

THE PREDICTION RESULT
---------------------
result = {
    "delayed":                    True,      # bool
    "delay_probability":          0.63,      # float 0-1
    "confidence":                 "medium",  # "high" / "medium" / "low"
    "predicted_duration_minutes": 7.2,       # float or None
    "duration_range":             {"low": 4.7, "high": 9.7},  # or None
    "code_used":                  "SUDP",    # what code the ML used
    "code_was_inferred":          True,      # True = ML chose the code
    "stage1_model_version":       "v20260307_055529",
    "stage2_model_version":       "v20260307_065006",
    "features_used": {
        "route_avg_delay":          1.43,
        "route_hour_avg_delay":     2.04,
        "route_day_hour_avg_delay": 4.0,
    }
}

HOW TO PHRASE THE RESPONSE - CONFIDENCE LEVELS
-----------------------------------------------
confidence == "high":
    State the prediction clearly.
    "There is a 73% chance of delays on Line 1 at Bloor around 5pm Thursday.
     If delayed, expect around 8 minutes (typically 5 to 11 minutes)."

confidence == "medium":
    Add a light hedge.
    "There is a moderate chance of delays (~58%) on Line 1 at Bloor around
     5pm Thursday. If delays occur, they tend to last around 8 minutes."

confidence == "low":
    Do not state a probability. Acknowledge uncertainty.
    "The model does not have strong signal for this route and time. Delays
     are possible but I cannot give a reliable estimate. Check TTC service
     alerts directly for current status."

WHEN ML SERVICE IS DOWN
-----------------------
If get_predictor() raises an exception or returns None, fall back to:
    "I am unable to check delay predictions right now. Please check
     ttc.ca or the TTC app for current service status."

IMPORTANT - THIS IS PREDICTIVE NOT LIVE
-----------------------------------------
The ML model predicts based on HISTORICAL PATTERNS.
It does NOT know about live service disruptions happening right now.
Always make this clear in responses. Never say "Line 1 is currently delayed."
Say instead "Line 1 tends to have delays at this time on Thursdays."

MULTI-TURN CONTEXT
------------------
The context dict passed into handle_message carries state between turns.
Store anything you need to remember between messages in it:
    context["last_line"]    = "Line 1"
    context["last_station"] = "BLOOR STATION"
This allows follow-up queries like "What about tomorrow?" to work.
The context dict is managed by main.py between requests for the same session_id.

SESSION IDs
-----------
Each user conversation has a unique session_id. Use it to keep context
separate between different users. main.py passes it through automatically.

VALID STATION NAMES
-------------------
Station names must be uppercase and match training data exactly.
The full list is in: data/processing/route_stats.csv (Station column)
Normalisation rule: uppercase + append " STATION" if not already present.
If a station does not match, the ML layer falls back gracefully - it will
not crash, but predictions will be less accurate.

VALID LINE NAMES
----------------
    "Line 1"    Yonge-University
    "Line 2"    Bloor-Danforth
    "Line 3"    (not in training data - handle gracefully)
    "Line 4"    Sheppard
    "Line 1/2"  interchange stations
"""
#---------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Any, Dict

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public interface - main.py calls this function
# ---------------------------------------------------------------------------

def handle_message(
    user_message: str,
    session_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
  
    """
    Process a user message and return a response.

    Parameters
    ----------
    user_message : str
        The raw message from the user exactly as typed.
    session_id   : str
        Unique identifier for this conversation session.
        Use to keep multi-turn context separate between users.
    context      : dict
        Mutable dict persisted between turns for this session.
        Read from it to recall previous entities.
        Write to it to remember things for the next turn.

    Returns
    -------
    dict with these keys:
        response  : str   - the natural language response to show the user
        data      : dict  - optional structured data for the frontend (can be None)
        ml_used   : bool  - whether the ML predictor was called

    Example return value:
        {
            "response": "There is a 63% chance of delays on Line 1 at Bloor
                         around 5pm Thursday. If delayed, expect around
                         7 minutes (typically 5 to 10 minutes).",
            "data": {
                "delayed": True,
                "delay_probability": 0.63,
                "line": "Line 1",
                "station": "BLOOR STATION",
            },
            "ml_used": True,
        }
    """
    # ------------------------------------------------------------------
    # STUB IMPLEMENTATION
    # Replace everything below with your actual NLP logic.
    # The structure of the return dict must stay the same.
    # ------------------------------------------------------------------

    log.info(f"[{session_id}] Received message: {user_message}")

    # TODO: implement intent detection
    # intent = detect_intent(user_message)
    # e.g. "delay_query", "general_ttc_question", "greeting", "out_of_scope"

    # TODO: implement entity extraction
    # entities = extract_entities(user_message, context)
    # e.g. {"line": "Line 1", "station": "Bloor", "hour": 17, ...}

    # TODO: implement ML call for delay queries
    # if intent == "delay_query":
    #     from models.src.predictor import get_predictor
    #     predictor = get_predictor()
    #     result = predictor.predict(**entities)
    #     response = format_prediction_response(result)
    #     return {"response": response, "data": result, "ml_used": True}

    # TODO: implement response generation for non-delay queries
    # Use your LLM/NLP approach for general TTC questions

    # Placeholder response until implemented
    return {
        "response": (
            "I can help you predict TTC delays. "
            "Try asking something like: "
            "'Will Line 1 be delayed at Bloor around 5pm on Thursday?'"
        ),
        "data": None,
        "ml_used": False,
    }


# ---------------------------------------------------------------------------
# SUGGESTED HELPER FUNCTIONS - implement these to build out handle_message()
# ---------------------------------------------------------------------------

def detect_intent(message: str) -> str:
    """
    Classify the user's intent.

    Suggested intents:
        "delay_query"           - user asking about delays on a specific route/time
        "general_ttc_question"  - general TTC question (schedules, fares, etc.)
        "greeting"              - hello, hi, hey
        "out_of_scope"          - nothing to do with TTC

    Returns one of the above strings.
    """
    # TODO: implement using your LLM or rule-based approach
    raise NotImplementedError("detect_intent() not yet implemented")


def extract_entities(
    message: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract structured entities from the user message.

    Should return a dict suitable for passing to predictor.predict():
        {
            "line":        "Line 1",
            "station":     "BLOOR STATION",
            "hour":        17,
            "day_of_week": 3,
            "is_weekend":  0,
            "month":       3,
            "week":        10,
            "year":        2026,
        }

    Use context to fill in missing entities from previous turns.
    e.g. if user says "What about tomorrow?" and context has last_line and
    last_station, carry those forward with the updated day/time.

    Station normalisation rule:
        station.upper() + " STATION" if "STATION" not in station.upper()
    """
    # TODO: implement using your LLM or rule-based approach
    raise NotImplementedError("extract_entities() not yet implemented")


def format_prediction_response(
    result: Dict[str, Any],
    line: str,
    station: str,
) -> str:
    """
    Convert the ML prediction result dict into a natural language response.

    Use the confidence level to control how strongly you state the prediction.
    See the CONFIDENCE LEVELS section at the top of this file.

    Never say "currently delayed" - this is a predictive model not live status.
    Always present duration as a range, never as a precise figure.
    """
    # TODO: implement response formatting
    raise NotImplementedError("format_prediction_response() not yet implemented")
