"""
TTC Model Registry
==================
Manages which trained artifact versions are active for inference.

Repo path:   models/src/registry.py
Registry file: models/trained/model_registry.json

The registry file looks like:
{
      "classification": {
            "active": "v20260301_120000",
            "available": ["v20260201_090000", "v20260301_120000"]
      },
      "regression": {
            "active": "v20260301_121500",
            "available": ["v20260201_090500", "v20260301_121500"]
      },
      "updated_at": "2026-03-01T12:15:00"
}

Usage
-----
      from registry import ModelRegistry

      registry = ModelRegistry()

      # Get the active artifact directory for each model type
      clf_dir = registry.get_active_dir("classification")
      reg_dir = registry.get_active_dir("regression")

      # Promote a specific version to active
      registry.promote("classification", "v20260301_120000")

      # Auto-promote latest available version
      registry.promote_latest("classification")

CLI
---
      python registry.py status
      python registry.py promote classification v20260301_120000
      python registry.py promote-latest classification
      python registry.py promote-latest all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

# Notifier is imported lazily inside promote() so registry.py can be used
# standalone (e.g. during initial setup before notifier dependencies exist).

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
TRAINED_ROOT: Path = _REPO_ROOT / "models" / "trained"
REGISTRY_PATH: Path = TRAINED_ROOT / "model_registry.json"

ModelType = Literal["classification", "regression"]
MODEL_TYPES: list[ModelType] = ["classification", "regression"]


class ModelRegistry:
      """
      Manages active model versions for the inference layer.

      Behaviour
      ---------
      - On first use, if no registry file exists, auto-promotes the latest
         available version of each model type.
      - Thread-safe for reads (registry file is read fresh on each call).
      - Writes are not concurrency-safe; run promotions from a single process
         (e.g., a deployment script), not from the inference service.
      """

      def __init__(self, registry_path: Path = REGISTRY_PATH):
            self.registry_path = registry_path
            self._ensure_registry_exists()

      # ------------------------------------------------------------------
      # Public API
      # ------------------------------------------------------------------

      def get_active_dir(self, model_type: ModelType) -> Path:
            """
            Return the artifact directory for the currently active version.

            Raises
            ------
            ValueError   if no active version is registered for model_type.
            FileNotFoundError   if the artifact directory does not exist on disk.
            """
            registry = self._load()
            entry = registry.get(model_type, {})
            active = entry.get("active")

            if not active:
                  raise ValueError(
                        f"No active version registered for '{model_type}'. "
                        f"Run: python registry.py promote-latest {model_type}"
                  )

            artifact_dir = TRAINED_ROOT / model_type / active
            if not artifact_dir.exists():
                  raise FileNotFoundError(
                        f"Artifact directory not found on disk: {artifact_dir}\n"
                        f"The registry may be out of sync. "
                        f"Run: python registry.py promote-latest {model_type}"
                  )

            return artifact_dir

      def get_active_version(self, model_type: ModelType) -> Optional[str]:
            """Return the active version string, or None if not set."""
            return self._load().get(model_type, {}).get("active")

      def list_available(self, model_type: ModelType) -> list[str]:
            """
            Return all available versions on disk, sorted chronologically
            (oldest first). Scans the artifact directory directly so it stays
            in sync even if the registry file is stale.
            """
            base = TRAINED_ROOT / model_type
            if not base.exists():
                  return []
            versions = sorted(
                  d.name for d in base.iterdir()
                  if d.is_dir() and d.name.startswith("v")
            )
            return versions

      def promote(self, model_type: ModelType, version: str, notify: bool = True) -> None:
            """
            Set a specific version as active.

            Parameters
            ----------
            model_type : "classification" or "regression"
            version      : Version string, e.g. "v20260301_120000"
            notify       : If True (default), trigger notifier after promotion —
                                restarts the ML service and sends webhooks to subscribers.
                                Pass notify=False during initial setup or batch promotions
                                where you want to promote both models before notifying.

            Raises
            ------
            FileNotFoundError   if the version directory does not exist on disk.
            """
            artifact_dir = TRAINED_ROOT / model_type / version
            if not artifact_dir.exists():
                  raise FileNotFoundError(
                        f"Cannot promote '{version}': "
                        f"directory not found at {artifact_dir}"
                  )

            # Snapshot the registry state before we change it so the notifier
            # can report what changed (previous vs current version).
            previous_registry = self._load()

            registry = self._load()
            available = self.list_available(model_type)

            registry[model_type] = {
                  "active":      version,
                  "available": available,
            }
            registry["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(registry)
            log.info(f"Promoted {model_type} → {version}")

            if notify:
                  try:
                        from notifier import on_promotion
                        on_promotion(
                              previous_registry=previous_registry,
                              current_registry=registry,
                        )
                  except ImportError:
                        log.warning(
                              "notifier.py not found — skipping webhook notifications. "
                              "Add notifier.py to models/src/ to enable notifications."
                        )

      def promote_latest(self, model_type: ModelType, notify: bool = True) -> Optional[str]:
            """
            Promote the most recently trained version to active.
            Returns the promoted version string, or None if none available.

            Parameters
            ----------
            notify : If True (default), trigger notifier after promotion.
                          Set to False when promoting multiple model types in sequence
                          so only one combined notification is sent at the end.
            """
            available = self.list_available(model_type)
            if not available:
                  log.warning(f"No trained versions found for '{model_type}'")
                  return None

            latest = available[-1]
            self.promote(model_type, latest, notify=notify)
            return latest

      def status(self) -> dict:
            """Return a summary of the current registry state."""
            result = {}
            for model_type in MODEL_TYPES:
                  active = self.get_active_version(model_type)
                  available = self.list_available(model_type)
                  result[model_type] = {
                        "active":      active,
                        "available": available,
                        "n_versions": len(available),
                  }
            return result

      # ------------------------------------------------------------------
      # Internal helpers
      # ------------------------------------------------------------------

      def _load(self) -> dict:
            if not self.registry_path.exists():
                  return {}
            with open(self.registry_path) as fh:
                  return json.load(fh)

      def _save(self, registry: dict) -> None:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "w") as fh:
                  json.dump(registry, fh, indent=4)

      def _ensure_registry_exists(self) -> None:
            """
            On first use, auto-promote the latest available version of each
            model type so the service works out of the box after training.
            """
            if self.registry_path.exists():
                  return

            log.info("No registry file found — initialising from available artifacts")
            for model_type in MODEL_TYPES:
                  version = self.promote_latest(model_type)
                  if version:
                        log.info(f"   Auto-promoted {model_type} → {version}")
                  else:
                        log.warning(
                              f"   No artifacts found for '{model_type}'. "
                              f"Train a model first: python ph1_{model_type}.py"
                        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_status(registry: ModelRegistry) -> None:
      status = registry.status()
      print("\nModel Registry Status")
      print("=" * 40)
      for model_type, info in status.items():
            print(f"\n{model_type.upper()}")
            print(f"   Active:      {info['active'] or 'NONE'}")
            print(f"   Available: {info['available']}")
      print()


def _cli_promote(registry: ModelRegistry, model_type: str, version: str) -> None:
      registry.promote(model_type, version)
      print(f"Promoted {model_type} → {version}")


def _cli_promote_latest(registry: ModelRegistry, model_type: str) -> None:
      targets = MODEL_TYPES if model_type == "all" else [model_type]
      for mt in targets:
            version = registry.promote_latest(mt)
            if version:
                  print(f"Promoted {mt} → {version}")
            else:
                  print(f"No versions available for {mt}")


if __name__ == "__main__":
      logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

      parser = argparse.ArgumentParser(description="TTC Model Registry")
      sub = parser.add_subparsers(dest="command")

      sub.add_parser("status", help="Show active and available versions")

      p_promote = sub.add_parser("promote", help="Promote a specific version to active")
      p_promote.add_argument("model_type", choices=MODEL_TYPES)
      p_promote.add_argument("version", help="e.g. v20260301_120000")

      p_latest = sub.add_parser("promote-latest", help="Promote the newest version to active")
      p_latest.add_argument("model_type", choices=[*MODEL_TYPES, "all"])

      args = parser.parse_args()
      reg = ModelRegistry()

      if args.command == "status":
            _cli_status(reg)
      elif args.command == "promote":
            _cli_promote(reg, args.model_type, args.version)
      elif args.command == "promote-latest":
            _cli_promote_latest(reg, args.model_type)
      else:
            parser.print_help()
            sys.exit(1)
