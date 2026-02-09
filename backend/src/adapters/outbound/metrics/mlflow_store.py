"""MLflow implementation of MetricsStorePort."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MLflowMetricsStore:
    """Implements :class:`MetricsStorePort` using the MLflow tracking client.

    Wraps :func:`mlflow.start_run`, :func:`mlflow.log_metric`,
    :func:`mlflow.log_params`, and :func:`mlflow.log_artifact` behind the port
    interface so that the core domain remains framework-agnostic.
    """

    def __init__(
        self,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "movie_cutter",
    ) -> None:
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name
        self._mlflow: Optional[Any] = None
        self._initialised = False

    # -- lazy initialisation ---------------------------------------------------

    def _ensure_mlflow(self) -> Any:
        """Import and configure mlflow on first use."""
        if self._mlflow is not None:
            return self._mlflow

        try:
            import mlflow  # type: ignore[import-untyped]

            mlflow.set_tracking_uri(self._tracking_uri)
            mlflow.set_experiment(self._experiment_name)
            self._mlflow = mlflow
            self._initialised = True
            logger.info(
                "MLflow initialised (uri=%s, experiment=%s)",
                self._tracking_uri,
                self._experiment_name,
            )
        except ImportError:
            logger.error(
                "mlflow is not installed. Install it with: pip install mlflow"
            )
            raise

        return self._mlflow

    # -- MetricsStorePort implementation ---------------------------------------

    def start_run(self, name: str, tags: dict | None = None) -> str:
        """Start a new MLflow run and return its run_id."""
        mlflow = self._ensure_mlflow()
        run = mlflow.start_run(run_name=name, tags=tags or {})
        run_id: str = run.info.run_id
        logger.debug("Started MLflow run %s (%s)", name, run_id)
        return run_id

    def log_metric(
        self, run_id: str, key: str, value: float, step: int = 0
    ) -> None:
        """Log a single metric value under the given run."""
        mlflow = self._ensure_mlflow()
        with mlflow.start_run(run_id=run_id):
            mlflow.log_metric(key, value, step=step)
        logger.debug("Logged metric %s=%.4f (step=%d, run=%s)", key, value, step, run_id)

    def log_params(self, run_id: str, params: dict) -> None:
        """Log a batch of parameters under the given run."""
        mlflow = self._ensure_mlflow()
        with mlflow.start_run(run_id=run_id):
            mlflow.log_params(params)
        logger.debug("Logged %d params for run %s", len(params), run_id)

    def log_artifact(self, run_id: str, filepath: str) -> None:
        """Log a local file as an artifact under the given run."""
        mlflow = self._ensure_mlflow()
        with mlflow.start_run(run_id=run_id):
            mlflow.log_artifact(filepath)
        logger.debug("Logged artifact %s for run %s", filepath, run_id)

    def end_run(self, run_id: str) -> None:
        """End an active MLflow run."""
        mlflow = self._ensure_mlflow()
        with mlflow.start_run(run_id=run_id):
            mlflow.end_run()
        logger.debug("Ended MLflow run %s", run_id)
