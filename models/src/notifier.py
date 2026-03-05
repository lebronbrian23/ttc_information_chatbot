
"""
TTC Model Update Notifier
=========================
Broadcasts model promotion events to all registered services and triggers
a graceful restart of the ML prediction service.

Repo path:   models/src/notifier.py

This module is called automatically by registry.py whenever a model version
is promoted. It does two things:

      1. Sends an HTTP POST webhook to every registered subscriber
           (backend, NLP service) so they know the model has changed.

      2. Triggers a graceful restart of the ML API service so it reloads
           the newly promoted model artifacts without dropping in-flight requests.

WEBHOOK PAYLOAD
---------------
Every subscriber receives the same JSON payload:

      {
            "event":          "model_promoted",
            "promoted_at": "2026-03-05T12:00:00+00:00",
            "changes": {
                  "classification": {
                        "previous": "v20260201_090000",
                        "current":   "v20260301_120000",
                        "changed":   true
                  },
                  "regression": {
                        "previous": "v20260201_090500",
                        "current":   "v20260301_121500",
                        "changed":   true
                  }
            },
            "ml_service_restarting": true
      }

SUBSCRIBER REGISTRATION
------------------------
Subscribers are registered in:

      models/trained/webhook_subscribers.json

      {
            "subscribers": [
                  {
                        "name":      "backend",
                        "url":       "http://localhost:3000/ml-updated",
                        "enabled": true
                  },
                  {
                        "name":      "nlp_service",
                        "url":       "http://localhost:5000/ml-updated",
                        "enabled": true
                  }
            ]
      }

Edit this file to add or remove subscribers. The ML service itself is
NOT in this list — it restarts via the graceful restart mechanism, not
via webhook.

WHAT SUBSCRIBERS SHOULD DO ON RECEIPT
--------------------------------------
When a subscriber receives the webhook:

      Backend:
      - Read changes.classification.current and changes.regression.current
      - Update any cached model version display in the UI
      - If caching any ML responses, flush the cache
      - Respond 200 OK once processed

      NLP service:
      - Read changes to know a new model is active
      - Flush any cached predictions
      - If prompts reference model version, update them
      - Respond 200 OK once processed

GRACEFUL RESTART
----------------
The ML API service (uvicorn) is restarted by sending SIGHUP to the
process. Uvicorn handles SIGHUP as a graceful reload — it:
      1. Stops accepting new connections
      2. Finishes all in-flight requests
      3. Reloads the application (picks up new model from registry)
      4. Resumes accepting connections

The PID of the running uvicorn process is stored in:
      models/trained/ml_service.pid

The ML service writes this file on startup (see api.py startup_event).

USAGE
-----
      # Called automatically by registry.py on promote — you don't need to
      # call this directly in normal operation.

      # But you can call it manually to test notifications:
      python notifier.py --dry-run               # shows what would be sent, no actual calls
      python notifier.py                              # sends notifications + restarts service

ENVIRONMENT VARIABLES
---------------------
      TTC_WEBHOOK_SECRET    — if set, all webhook POSTs include an
                                         X-TTC-Signature header (HMAC-SHA256 of the
                                         payload) so subscribers can verify authenticity.
                                         Set the same value on all subscriber services.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request as urllib_request
from urllib.error import URLError

log = logging.getLogger(__name__)

_REPO_ROOT            = Path(__file__).resolve().parents[2]
TRAINED_ROOT         = _REPO_ROOT / "models" / "trained"
REGISTRY_PATH       = TRAINED_ROOT / "model_registry.json"
SUBSCRIBERS_PATH   = TRAINED_ROOT / "webhook_subscribers.json"
PID_FILE_PATH       = TRAINED_ROOT / "ml_service.pid"

WEBHOOK_TIMEOUT_SECONDS = 5
WEBHOOK_SECRET = os.getenv("TTC_WEBHOOK_SECRET", "")


# ---------------------------------------------------------------------------
# Subscriber management
# ---------------------------------------------------------------------------

def load_subscribers() -> List[Dict[str, Any]]:
      """
      Load registered webhook subscribers from webhook_subscribers.json.
      Returns an empty list if the file doesn't exist (no subscribers registered yet).
      """
      if not SUBSCRIBERS_PATH.exists():
            log.info(
                  f"No subscribers file found at {SUBSCRIBERS_PATH}. "
                  f"Create it to register backend/NLP webhook endpoints."
            )
            return []

      with open(SUBSCRIBERS_PATH) as fh:
            data = json.load(fh)

      subscribers = [s for s in data.get("subscribers", []) if s.get("enabled", True)]
      log.info(f"Loaded {len(subscribers)} active subscriber(s)")
      return subscribers


def register_subscriber(name: str, url: str) -> None:
      """
      Add a new subscriber to webhook_subscribers.json.
      Creates the file if it doesn't exist.
      Safe to call multiple times — won't duplicate entries.
      """
      if SUBSCRIBERS_PATH.exists():
            with open(SUBSCRIBERS_PATH) as fh:
                  data = json.load(fh)
      else:
            data = {"subscribers": []}

      existing_names = {s["name"] for s in data["subscribers"]}
      if name in existing_names:
            log.info(f"Subscriber '{name}' already registered — updating URL")
            for s in data["subscribers"]:
                  if s["name"] == name:
                        s["url"] = url
                        s["enabled"] = True
      else:
            data["subscribers"].append({"name": name, "url": url, "enabled": True})
            log.info(f"Registered new subscriber: {name} → {url}")

      SUBSCRIBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
      with open(SUBSCRIBERS_PATH, "w") as fh:
            json.dump(data, fh, indent=4)


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def build_payload(
      previous_registry: Dict[str, Any],
      current_registry: Dict[str, Any],
      ml_service_restarting: bool,
) -> Dict[str, Any]:
      """
      Build the webhook payload describing what changed in this promotion.
      """
      changes: Dict[str, Any] = {}
      for model_type in ("classification", "regression"):
            prev = previous_registry.get(model_type, {}).get("active")
            curr = current_registry.get(model_type, {}).get("active")
            changes[model_type] = {
                  "previous": prev,
                  "current":   curr,
                  "changed":   prev != curr,
            }

      return {
            "event":                        "model_promoted",
            "promoted_at":               datetime.now(timezone.utc).isoformat(),
            "changes":                     changes,
            "ml_service_restarting": ml_service_restarting,
      }


# ---------------------------------------------------------------------------
# Webhook delivery
# ---------------------------------------------------------------------------

def _sign_payload(payload_bytes: bytes) -> Optional[str]:
      """Return HMAC-SHA256 signature if a secret is configured, else None."""
      if not WEBHOOK_SECRET:
            return None
      sig = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload_bytes,
            hashlib.sha256,
      ).hexdigest()
      return f"sha256={sig}"


def send_webhook(subscriber: Dict[str, Any], payload: Dict[str, Any], dry_run: bool = False) -> bool:
      """
      POST the payload to a single subscriber URL.

      Returns True on success, False on failure.
      Failures are logged but never raise — a failed notification must
      never block or crash the promotion process.
      """
      name = subscriber["name"]
      url   = subscriber["url"]

      payload_bytes = json.dumps(payload).encode("utf-8")
      signature       = _sign_payload(payload_bytes)

      if dry_run:
            log.info(f"[DRY RUN] Would POST to {name} ({url})")
            log.info(f"[DRY RUN] Payload: {json.dumps(payload, indent=2)}")
            if signature:
                  log.info(f"[DRY RUN] Signature: {signature}")
            return True

      headers = {"Content-Type": "application/json"}
      if signature:
            headers["X-TTC-Signature"] = signature

      try:
            req = urllib_request.Request(url, data=payload_bytes, headers=headers, method="POST")
            with urllib_request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS) as resp:
                  status = resp.status
                  if 200 <= status < 300:
                        log.info(f"Notified {name} ({url}) → HTTP {status}")
                        return True
                  else:
                        log.warning(f"Notification to {name} returned HTTP {status}")
                        return False
      except URLError as exc:
            log.warning(
                  f"Could not reach {name} ({url}): {exc}. "
                  f"Service may not be running yet — this is non-fatal."
            )
            return False
      except Exception as exc:
            log.error(f"Unexpected error notifying {name} ({url}): {exc}")
            return False


def notify_all(
      payload: Dict[str, Any],
      dry_run: bool = False,
) -> Dict[str, bool]:
      """
      Send the webhook payload to all registered subscribers.

      Returns a dict of {subscriber_name: success_bool} for logging/reporting.
      Never raises — failures are recorded but don't block promotion.
      """
      subscribers = load_subscribers()

      if not subscribers:
            log.info("No subscribers registered — skipping webhook notifications")
            return {}

      results = {}
      for subscriber in subscribers:
            results[subscriber["name"]] = send_webhook(subscriber, payload, dry_run=dry_run)

      successes = sum(results.values())
      log.info(
            f"Webhook notifications: {successes}/{len(results)} delivered successfully"
      )
      return results


# ---------------------------------------------------------------------------
# Graceful ML service restart
# ---------------------------------------------------------------------------

def restart_ml_service(dry_run: bool = False) -> bool:
      """
      Send SIGHUP to the running uvicorn process to trigger a graceful reload.

      Uvicorn's graceful reload:
            1. Stops accepting new requests
            2. Waits for in-flight requests to complete
            3. Reloads the application (picks up new model from registry)
            4. Resumes accepting requests

      The PID is read from ml_service.pid, which api.py writes on startup.

      Returns True if the signal was sent successfully, False otherwise.
      """
      if not PID_FILE_PATH.exists():
            log.warning(
                  f"PID file not found at {PID_FILE_PATH}. "
                  f"ML service may not be running, or api.py hasn't been updated "
                  f"to write the PID file on startup."
            )
            return False

      try:
            pid = int(PID_FILE_PATH.read_text().strip())
      except (ValueError, IOError) as exc:
            log.error(f"Could not read PID from {PID_FILE_PATH}: {exc}")
            return False

      if dry_run:
            log.info(f"[DRY RUN] Would send SIGHUP to ML service (PID {pid})")
            return True

      try:
            os.kill(pid, signal.SIGHUP)
            log.info(f"Sent SIGHUP to ML service (PID {pid}) — graceful reload initiated")
            return True
      except ProcessLookupError:
            log.warning(
                  f"No process found with PID {pid}. "
                  f"ML service is not running. PID file may be stale."
            )
            PID_FILE_PATH.unlink(missing_ok=True)
            return False
      except PermissionError:
            log.error(
                  f"Permission denied sending signal to PID {pid}. "
                  f"Run the notifier as the same user that started the ML service."
            )
            return False


# ---------------------------------------------------------------------------
# Main entry point — called by registry.py after every promotion
# ---------------------------------------------------------------------------

def on_promotion(
      previous_registry: Dict[str, Any],
      current_registry: Dict[str, Any],
      dry_run: bool = False,
) -> None:
      """
      Called by registry.py immediately after a version is promoted.

      Sequence:
            1. Restart ML service (graceful — in-flight requests finish first)
            2. Wait briefly for service to reload
            3. Notify all subscribers (backend, NLP) with the change payload
      """
      ml_restarting = restart_ml_service(dry_run=dry_run)

      if ml_restarting and not dry_run:
            # Give the service a moment to begin its reload before we notify
            # subscribers that it is restarting, so they don't immediately
            # hit the service before it has reloaded.
            log.info("Waiting 3s for ML service to begin graceful reload...")
            time.sleep(3)

      payload = build_payload(previous_registry, current_registry, ml_restarting)
      notify_all(payload, dry_run=dry_run)

      log.info("Promotion notification sequence complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
      logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
      )

      parser = argparse.ArgumentParser(
            description="TTC Model Update Notifier"
      )
      parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without making any actual calls or restarts",
      )
      parser.add_argument(
            "--register",
            nargs=2,
            metavar=("NAME", "URL"),
            help="Register a new webhook subscriber, e.g. --register backend http://localhost:3000/ml-updated",
      )
      args = parser.parse_args()

      if args.register:
            name, url = args.register
            register_subscriber(name, url)
            log.info(f"Subscriber '{name}' registered at {url}")
            sys.exit(0)

      # Manual trigger — reads current registry as both prev and current
      # (for testing notification delivery without an actual promotion)
      if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH) as fh:
                  registry = json.load(fh)
      else:
            registry = {}

      on_promotion(
            previous_registry=registry,
            current_registry=registry,
            dry_run=args.dry_run,
      )
