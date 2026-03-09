"""
TTC Model Retraining Scheduler
================================
Runs the full retraining pipeline on a configurable schedule.
Pure Python — no cron required. Works on any cloud platform that
can run a persistent Python process.

Repo path:   models/src/scheduler.py
Date: Mar 6 2026

HOW IT WORKS
------------
The scheduler runs as a long-lived background process alongside the ML
service. It wakes up on the configured schedule, runs retrain.sh, then
goes back to sleep. Everything else (service restart, notifications) is
handled by retrain.sh → registry.py → notifier.py.

SCHEDULE OPTIONS
----------------
Configure in scheduler_config.json (auto-created on first run):

      {
            "schedule": "weekly",          // "weekly", "monthly", or "on_demand"
            "day_of_week": "sunday",      // for weekly: which day to retrain
            "hour": 2,                           // hour of day to run (24h, server time)
            "minute": 0,
            "retrain_args": "--no-tune" // extra args passed to retrain.sh (optional)
      }

      "on_demand" means the scheduler does NOT run automatically — you
      trigger it manually via the CLI (useful during development).

CLOUD DEPLOYMENT
----------------
On any cloud platform, run this as a background process alongside api.py:

      # Start both together
      python models/src/scheduler.py &
      uvicorn models/src/api:app --host 0.0.0.0 --port 8000

      # Or keep them in separate processes/containers
      python models/src/scheduler.py    # dedicated scheduler process

The scheduler writes its status to:
      models/trained/scheduler_status.json

This file is read by the /scheduler-status endpoint in api.py so you
can check when the last retrain ran and when the next one is scheduled.

CLI USAGE
---------
      # Start the scheduler (runs continuously)
      python scheduler.py

      # Trigger an immediate retrain right now (ignores schedule)
      python scheduler.py --run-now

      # Check status (last run, next run, config)
      python scheduler.py --status

      # Change the schedule
      python scheduler.py --set-schedule weekly --day sunday --hour 2
      python scheduler.py --set-schedule monthly --hour 3
      python scheduler.py --set-schedule on_demand
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = Path(__file__).resolve().parent
RETRAIN_SCRIPT = SRC_DIR / "retrain.sh"
TRAINED_ROOT = _REPO_ROOT / "models" / "trained"
CONFIG_PATH = TRAINED_ROOT / "scheduler_config.json"
STATUS_PATH = TRAINED_ROOT / "scheduler_status.json"

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday",
                "thursday", "friday", "saturday", "sunday"]

DEFAULT_CONFIG: Dict[str, Any] = {
    "schedule":       "weekly",
    "day_of_week":   "sunday",
    "hour":             2,
    "minute":          0,
    "retrain_args": "",
}

# How often the scheduler wakes up to check if it's time to retrain (seconds)
# 60s means it checks once per minute — low overhead, accurate to the minute
POLL_INTERVAL_SECONDS = 60


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------

def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        log.info(f"No config found — creating default config at {CONFIG_PATH}")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_PATH) as fh:
        return {**DEFAULT_CONFIG, **json.load(fh)}


def save_config(config: Dict[str, Any]) -> None:
    TRAINED_ROOT.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as fh:
        json.dump(config, fh, indent=4)


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

def load_status() -> Dict[str, Any]:
    if not STATUS_PATH.exists():
        return {
            "last_run_at":       None,
            "last_run_result": None,
            "next_run_at":       None,
            "runs_completed":   0,
            "runs_failed":       0,
        }
    with open(STATUS_PATH) as fh:
        return json.load(fh)


def save_status(status: Dict[str, Any]) -> None:
    TRAINED_ROOT.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "w") as fh:
        json.dump(status, fh, indent=4, default=str)


# ---------------------------------------------------------------------------
# Schedule calculation
# ---------------------------------------------------------------------------

def next_run_time(config: Dict[str, Any]) -> Optional[datetime]:
    """
    Calculate when the next retrain should run based on the config.
    Returns None if schedule is "on_demand".
    """
    if config["schedule"] == "on_demand":
        return None

    now = datetime.now(timezone.utc)
    hour = config.get("hour", 2)
    minute = config.get("minute", 0)

    if config["schedule"] == "weekly":
        target_dow = DAYS_OF_WEEK.index(config.get("day_of_week", "sunday"))
        current_dow = now.weekday()    # 0=Monday

        days_ahead = (target_dow - current_dow) % 7
        if days_ahead == 0:
            # It's today — check if the time has already passed
            scheduled_today = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if now >= scheduled_today:
                days_ahead = 7    # already passed today, schedule for next week

        next_run = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return next_run

    elif config["schedule"] == "monthly":
        # Run on the 1st of next month at the configured hour
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)

        next_run = next_month.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        # If the 1st already passed this month, check if we're before it
        this_month_run = now.replace(
            day=1, hour=hour, minute=minute, second=0, microsecond=0
        )
        if now < this_month_run:
            return this_month_run
        return next_run

    return None


def is_due(config: Dict[str, Any], last_run_at: Optional[str]) -> bool:
    """
    Return True if a retrain is due right now based on the schedule.
    """
    if config["schedule"] == "on_demand":
        return False

    now = datetime.now(timezone.utc)
    hour = config.get("hour", 2)
    minute = config.get("minute", 0)

    # Check if we're in the right minute window
    if now.hour != hour or now.minute != minute:
        return False

    # Check we haven't already run in the last hour (prevent double-running)
    if last_run_at:
        last = datetime.fromisoformat(last_run_at)
        if (now - last).total_seconds() < 3600:
            return False

    if config["schedule"] == "weekly":
        target_dow = DAYS_OF_WEEK.index(config.get("day_of_week", "sunday"))
        return now.weekday() == target_dow

    elif config["schedule"] == "monthly":
        return now.day == 1

    return False


# ---------------------------------------------------------------------------
# Retraining execution
# ---------------------------------------------------------------------------

def run_retrain(retrain_args: str = "") -> bool:
    """
    Execute retrain.sh and return True on success, False on failure.
    Output is streamed to the scheduler's log in real time.
    """
    if not RETRAIN_SCRIPT.exists():
        log.error(f"retrain.sh not found at {RETRAIN_SCRIPT}")
        return False

    cmd = ["bash", str(RETRAIN_SCRIPT)]
    if retrain_args:
        cmd.extend(retrain_args.split())

    log.info(f"Starting retrain: {' '.join(cmd)}")
    start = datetime.now(timezone.utc)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            capture_output=False,    # stream output directly to terminal/log
            text=True,
        )
        duration = (datetime.now(timezone.utc) - start).total_seconds()
        success = result.returncode == 0

        if success:
            log.info(f"Retrain completed successfully in {duration:.0f}s")
        else:
            log.error(
                f"Retrain failed (exit code {result.returncode}) after {duration:.0f}s")

        return success

    except Exception as exc:
        log.error(f"Failed to run retrain.sh: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main scheduler loop
# ---------------------------------------------------------------------------

def run_scheduler() -> None:
    """
    Main loop — polls every POLL_INTERVAL_SECONDS and runs retrain when due.
    Runs indefinitely until interrupted (Ctrl+C or process kill).
    """
    log.info("TTC Retraining Scheduler started")
    config = load_config()
    log.info(
        f"Schedule: {config['schedule']} | "
        f"Day: {config.get('day_of_week', 'N/A')} | "
        f"Time: {config.get('hour', 2):02d}:{config.get('minute', 0):02d} UTC"
    )

    if config["schedule"] == "on_demand":
        log.info(
            "Schedule is 'on_demand' — scheduler will not run automatically. "
            "Use: python scheduler.py --run-now to trigger a retrain."
        )

    next_run = next_run_time(config)
    if next_run:
        log.info(
            f"Next scheduled retrain: {next_run.strftime('%Y-%m-%d %H:%M UTC')}")

    # Update status with next run time
    status = load_status()
    status["next_run_at"] = next_run.isoformat() if next_run else None
    save_status(status)

    try:
        while True:
            # Reload config on each poll so changes take effect without restart
            config = load_config()
            status = load_status()

            if is_due(config, status.get("last_run_at")):
                log.info("Retrain is due — starting now")

                success = run_retrain(config.get("retrain_args", ""))

                now = datetime.now(timezone.utc).isoformat()
                status["last_run_at"] = now
                status["last_run_result"] = "success" if success else "failed"

                if success:
                    status["runs_completed"] = status.get(
                        "runs_completed", 0) + 1
                else:
                    status["runs_failed"] = status.get("runs_failed", 0) + 1

                # Calculate and store next run time
                next_run = next_run_time(config)
                status["next_run_at"] = next_run.isoformat() if next_run else None
                save_status(status)

                if next_run:
                    log.info(
                        f"Next retrain scheduled: "
                        f"{next_run.strftime('%Y-%m-%d %H:%M UTC')}"
                    )

            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cli_status() -> None:
    config = load_config()
    status = load_status()
    next_run = next_run_time(config)

    print("\nTTC Retraining Scheduler — Status")
    print("=" * 45)
    print(f"   Schedule:          {config['schedule']}")
    if config["schedule"] == "weekly":
        print(
            f"   Day:                  {config.get('day_of_week', 'sunday').capitalize()}")
    print(
        f"   Time (UTC):       {config.get('hour', 2):02d}:{config.get('minute', 0):02d}")
    print(f"   Extra args:       {config.get('retrain_args') or '(none)'}")
    print()
    print(f"   Last run:          {status.get('last_run_at') or 'Never'}")
    print(f"   Last result:      {status.get('last_run_result') or 'N/A'}")
    print(
        f"   Next run:          {next_run.strftime('%Y-%m-%d %H:%M UTC') if next_run else 'On demand only'}")
    print(f"   Runs completed: {status.get('runs_completed', 0)}")
    print(f"   Runs failed:      {status.get('runs_failed', 0)}")
    print()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(
        description="TTC Model Retraining Scheduler")

    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Trigger an immediate retrain right now, ignoring the schedule",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current schedule config and last/next run times",
    )
    parser.add_argument(
        "--set-schedule",
        choices=["weekly", "monthly", "on_demand"],
        help="Change the retraining schedule",
    )
    parser.add_argument(
        "--day",
        choices=DAYS_OF_WEEK,
        help="Day of week for weekly schedule (e.g. sunday)",
    )
    parser.add_argument(
        "--hour",
        type=int,
        choices=range(24),
        metavar="HOUR",
        help="Hour of day to run (0-23, UTC)",
    )
    parser.add_argument(
        "--no-tune",
        action="store_true",
        help="Pass --no-tune to retrain.sh (skips hyperparameter search)",
    )

    args = parser.parse_args()

    if args.status:
        cli_status()

    elif args.set_schedule:
        config = load_config()
        config["schedule"] = args.set_schedule
        if args.day:
            config["day_of_week"] = args.day
        if args.hour is not None:
            config["hour"] = args.hour
        if args.no_tune:
            config["retrain_args"] = "--no-tune"
        save_config(config)
        log.info(f"Schedule updated: {config['schedule']}")
        cli_status()

    elif args.run_now:
        config = load_config()
        retrain_args = config.get("retrain_args", "")
        if args.no_tune:
            retrain_args = "--no-tune"
        log.info("Manual retrain triggered")
        success = run_retrain(retrain_args)
        sys.exit(0 if success else 1)

    else:
        # Default: start the scheduler loop
        if args.no_tune:
            config = load_config()
            config["retrain_args"] = "--no-tune"
            save_config(config)
        run_scheduler()
