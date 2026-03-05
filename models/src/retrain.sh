#!/bin/bash
# =============================================================================
# TTC Delay Model — Full Retraining Pipeline
# =============================================================================
# Runs the complete retraining sequence in order:
#   1. Train classification model
#   2. Train regression model
#   3. Rebuild feature lookup table
#   4. Promote new versions to active (triggers service restart + notifications)
#
# Repo path:  models/src/retrain.sh
#
# Usage
# -----
#   bash models/src/retrain.sh                        # full retrain
#   bash models/src/retrain.sh --no-tune              # skip hyperparameter tuning (faster)
#   bash models/src/retrain.sh --data path/to/data    # override data path
#
# Logs
# ----
#   All output is written to logs/retrain_YYYYMMDD_HHMMSS.log
#   The last run is also symlinked to logs/retrain_latest.log
#
# Exit codes
# ----------
#   0  success
#   1  one or more steps failed — check the log
# =============================================================================

set -euo pipefail   # exit on error, treat unset vars as error, fail on pipe errors

# ---------------------------------------------------------------------------
# Paths — all relative to repo root so the script works anywhere
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$REPO_ROOT/models/src"
LOG_DIR="$REPO_ROOT/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/retrain_$TIMESTAMP.log"
LATEST_LINK="$LOG_DIR/retrain_latest.log"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
TUNE_FLAG=""
DATA_FLAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-tune)
            TUNE_FLAG="--no-tune"
            shift
            ;;
        --data)
            DATA_FLAG="--data $2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: bash retrain.sh [--no-tune] [--data path/to/data.csv]"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"

# Tee all output to both terminal and log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================"
echo " TTC Delay Model — Retraining Pipeline"
echo " Started:    $(date)"
echo " Repo root:  $REPO_ROOT"
echo " Log file:   $LOG_FILE"
echo " Tune flag:  ${TUNE_FLAG:-'(tuning enabled)'}"
echo "============================================================"
echo ""

# Track overall success
FAILED_STEPS=()

# ---------------------------------------------------------------------------
# Helper: run a step and track failures without exiting early
# ---------------------------------------------------------------------------
run_step() {
    local step_name="$1"
    shift
    echo "------------------------------------------------------------"
    echo "STEP: $step_name"
    echo "Command: $*"
    echo "Time: $(date)"
    echo "------------------------------------------------------------"

    if "$@"; then
        echo "✓ $step_name completed successfully"
    else
        echo "✗ $step_name FAILED (exit code $?)"
        FAILED_STEPS+=("$step_name")
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Step 1: Classification model
# ---------------------------------------------------------------------------
run_step "Train Classification Model" \
    python "$SRC_DIR/ph1_classification.py" $TUNE_FLAG $DATA_FLAG

# ---------------------------------------------------------------------------
# Step 2: Regression model
# ---------------------------------------------------------------------------
run_step "Train Regression Model" \
    python "$SRC_DIR/ph1_regression.py" $TUNE_FLAG $DATA_FLAG

# ---------------------------------------------------------------------------
# Step 3: Rebuild feature lookup table
# ---------------------------------------------------------------------------
run_step "Build Feature Lookup Table" \
    python "$SRC_DIR/build_lookup.py" $DATA_FLAG

# ---------------------------------------------------------------------------
# Step 4: Promote new versions (triggers restart + notifications)
# ---------------------------------------------------------------------------
# Only promote if both training steps succeeded — no point promoting a
# partially failed retrain.
if [[ ${#FAILED_STEPS[@]} -eq 0 ]]; then
    run_step "Promote New Model Versions" \
        python "$SRC_DIR/registry.py" promote-latest all
else
    echo "------------------------------------------------------------"
    echo "SKIPPING promotion — training steps failed: ${FAILED_STEPS[*]}"
    echo "Previous model versions remain active."
    echo "------------------------------------------------------------"
    echo ""
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "============================================================"
echo " Retraining Pipeline — Summary"
echo " Finished: $(date)"
echo ""

if [[ ${#FAILED_STEPS[@]} -eq 0 ]]; then
    echo " Status: SUCCESS — all steps completed"
    echo " New models are now active and the service has been notified."
else
    echo " Status: FAILED — the following steps did not complete:"
    for step in "${FAILED_STEPS[@]}"; do
        echo "   - $step"
    done
    echo ""
    echo " Previous model versions remain active."
    echo " Check the log for details: $LOG_FILE"
fi

echo " Log: $LOG_FILE"
echo "============================================================"

# Update the latest log symlink
ln -sf "$LOG_FILE" "$LATEST_LINK"

# Exit with failure if any step failed
if [[ ${#FAILED_STEPS[@]} -gt 0 ]]; then
    exit 1
fi

exit 0
