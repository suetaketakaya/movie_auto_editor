"""
Experiment tracking with MLflow integration.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ExperimentTracker:
    """Tracks experiments via MLflow (or file-based fallback)."""

    def __init__(self, tracking_uri: str = "http://localhost:5000", experiment_name: str = "clipmontage"):
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name
        self._mlflow = None
        self._run_id: Optional[str] = None
        self._init_mlflow()

    def _init_mlflow(self):
        try:
            import mlflow
            mlflow.set_tracking_uri(self._tracking_uri)
            mlflow.set_experiment(self._experiment_name)
            self._mlflow = mlflow
            logger.info("MLflow connected: %s", self._tracking_uri)
        except Exception as e:
            logger.warning("MLflow not available, using file-based tracking: %s", e)
            self._mlflow = None

    def start_run(self, name: str, tags: Optional[dict] = None) -> str:
        """Start a new experiment run."""
        if self._mlflow:
            run = self._mlflow.start_run(run_name=name, tags=tags or {})
            self._run_id = run.info.run_id
            return self._run_id
        self._run_id = name
        return name

    def end_run(self) -> None:
        if self._mlflow:
            self._mlflow.end_run()
        self._run_id = None

    def log_trial(
        self,
        trial_num: int,
        params: dict,
        reward: float,
        sub_metrics: Optional[dict] = None,
    ) -> None:
        """Log a single trial."""
        if self._mlflow:
            self._mlflow.log_metric("reward", reward, step=trial_num)
            for key, value in (sub_metrics or {}).items():
                self._mlflow.log_metric(key, float(value), step=trial_num)
            if trial_num == 1:
                self._mlflow.log_params(
                    {k: str(v) for k, v in params.items()}
                )
        logger.info("Trial %d: reward=%.4f params=%s", trial_num, reward, params)

    def log_ablation(
        self,
        name: str,
        removed_component: str,
        baseline_reward: float,
        ablated_reward: float,
    ) -> None:
        """Log ablation study result."""
        delta = baseline_reward - ablated_reward
        if self._mlflow:
            self._mlflow.log_metric(f"ablation_{removed_component}_delta", delta)
            self._mlflow.log_metric(f"ablation_{removed_component}_reward", ablated_reward)
        logger.info(
            "Ablation %s: removed=%s baseline=%.4f ablated=%.4f delta=%.4f",
            name, removed_component, baseline_reward, ablated_reward, delta,
        )

    def log_artifact(self, filepath: str) -> None:
        """Log a file artifact (graph, PDF, etc.)."""
        if self._mlflow:
            self._mlflow.log_artifact(filepath)
        logger.info("Artifact logged: %s", filepath)

    def log_params(self, params: dict) -> None:
        if self._mlflow:
            self._mlflow.log_params({k: str(v) for k, v in params.items()})
