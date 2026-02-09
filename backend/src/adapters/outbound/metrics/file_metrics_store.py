"""File-based implementation of MetricsStorePort.

Fallback when MLflow is not available.  Stores all metrics, parameters, and
artifact references as JSON files on the local filesystem.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FileMetricsStore:
    """Implements :class:`MetricsStorePort` by persisting data as JSON files.

    Directory layout::

        <base_dir>/
            <run_id>/
                meta.json       # run name, tags, timestamps
                params.json     # logged parameters
                metrics.json    # metric history keyed by metric name
                artifacts/      # copied artifact files
    """

    def __init__(self, base_dir: str | Path = "metrics_store") -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)
        logger.info("FileMetricsStore initialised at %s", self._base)

    # -- helpers ---------------------------------------------------------------

    def _run_dir(self, run_id: str) -> Path:
        return self._base / run_id

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # -- MetricsStorePort implementation ---------------------------------------

    def start_run(self, name: str, tags: dict | None = None) -> str:
        """Create a new run directory and return its unique id."""
        run_id = str(uuid.uuid4())
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts").mkdir(exist_ok=True)

        meta = {
            "run_id": run_id,
            "name": name,
            "tags": tags or {},
            "started_at": datetime.utcnow().isoformat(),
            "ended_at": None,
        }
        self._write_json(run_dir / "meta.json", meta)
        self._write_json(run_dir / "params.json", {})
        self._write_json(run_dir / "metrics.json", {})

        logger.debug("Started file-backed run %s (%s)", name, run_id)
        return run_id

    def log_metric(
        self, run_id: str, key: str, value: float, step: int = 0
    ) -> None:
        """Append a metric data-point to the run's metrics file."""
        metrics_path = self._run_dir(run_id) / "metrics.json"
        metrics: dict[str, list[dict]] = self._read_json(metrics_path)
        metrics.setdefault(key, []).append(
            {
                "value": value,
                "step": step,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self._write_json(metrics_path, metrics)
        logger.debug(
            "Logged metric %s=%.4f (step=%d, run=%s)", key, value, step, run_id
        )

    def log_params(self, run_id: str, params: dict) -> None:
        """Merge *params* into the run's parameter file."""
        params_path = self._run_dir(run_id) / "params.json"
        existing: dict = self._read_json(params_path)
        existing.update(params)
        self._write_json(params_path, existing)
        logger.debug("Logged %d params for run %s", len(params), run_id)

    def log_artifact(self, run_id: str, filepath: str) -> None:
        """Copy a local file into the run's ``artifacts/`` directory."""
        source = Path(filepath)
        if not source.exists():
            logger.warning("Artifact source does not exist: %s", filepath)
            return
        dest = self._run_dir(run_id) / "artifacts" / source.name
        shutil.copy2(str(source), str(dest))
        logger.debug("Logged artifact %s -> %s for run %s", source, dest, run_id)

    def end_run(self, run_id: str) -> None:
        """Mark the run as ended by updating its metadata."""
        meta_path = self._run_dir(run_id) / "meta.json"
        meta: dict = self._read_json(meta_path)
        meta["ended_at"] = datetime.utcnow().isoformat()
        self._write_json(meta_path, meta)
        logger.debug("Ended file-backed run %s", run_id)
