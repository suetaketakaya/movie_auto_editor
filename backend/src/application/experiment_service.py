"""
Experiment management use case for RL-based optimization.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from backend.src.core.entities.experiment import Experiment, ExperimentStatus, Trial
from backend.src.core.value_objects.reward_signal import RewardSignal

logger = logging.getLogger(__name__)


class ExperimentService:
    """Manages RL experiments: create, run trials, query results."""

    def __init__(self, metrics_store, project_repository, experiment_repo=None):
        self._metrics_store = metrics_store
        self._project_repository = project_repository
        self._experiment_repo = experiment_repo
        self._run_id: Optional[str] = None

    async def create_experiment(
        self,
        name: str,
        parameter_space: dict,
        max_trials: int = 50,
        description: str = "",
    ) -> Experiment:
        experiment = Experiment(
            id=str(uuid.uuid4()),
            name=name,
            parameter_space=parameter_space,
            description=description,
        )

        # Start metrics run
        self._run_id = self._metrics_store.start_run(name, tags={"experiment_id": experiment.id})

        # Log parameters
        self._metrics_store.log_params(self._run_id, {
            "experiment_id": experiment.id,
            "experiment_name": name,
            "max_trials": str(max_trials),
        })

        # Save to repository if available
        if self._experiment_repo:
            await self._experiment_repo.save(experiment)

        logger.info("Experiment created: %s (%s)", experiment.id, name)
        return experiment

    async def record_trial(
        self,
        experiment: Experiment,
        parameters: dict,
        reward: float,
        metrics: dict,
    ) -> Trial:
        reward_signal = RewardSignal(total=reward, components=metrics)
        trial = Trial(
            trial_num=len(experiment.trials) + 1,
            parameters=parameters,
            reward=reward_signal,
            sub_metrics=metrics,
        )
        experiment.add_trial(trial)

        # Log to metrics store
        if self._run_id:
            self._metrics_store.log_metric(self._run_id, "reward", reward, step=trial.trial_num)
            for key, value in metrics.items():
                self._metrics_store.log_metric(
                    self._run_id, f"trial_{key}", float(value), step=trial.trial_num
                )

        # Persist trial if repo available
        if self._experiment_repo:
            await self._experiment_repo.add_trial(experiment.id, trial)

        return trial

    async def get_experiment_results(self, experiment_id: str) -> dict:
        # Try to get from repo first
        if self._experiment_repo:
            experiment = await self._experiment_repo.get_by_id(experiment_id)
            if experiment:
                return {
                    "experiment_id": experiment_id,
                    "trials": len(experiment.trials),
                    "reward_history": [
                        {"trial": t.trial_num, "reward": t.reward.total if t.reward else 0}
                        for t in experiment.trials
                    ],
                    "best_trial": {
                        "trial_num": experiment.best_trial.trial_num,
                        "reward": experiment.best_trial.reward.total if experiment.best_trial and experiment.best_trial.reward else 0,
                        "parameters": experiment.best_trial.parameters if experiment.best_trial else {},
                    } if experiment.best_trial else None,
                }

        # Fallback to empty result
        return {
            "experiment_id": experiment_id,
            "trials": 0,
            "reward_history": [],
        }

    async def get_convergence_data(self, experiment_id: str) -> list[dict]:
        if self._experiment_repo:
            experiment = await self._experiment_repo.get_by_id(experiment_id)
            if experiment:
                return [
                    {
                        "trial": t.trial_num,
                        "reward": t.reward.total if t.reward else 0,
                        "timestamp": t.timestamp.isoformat(),
                    }
                    for t in experiment.trials
                ]
        return []

    async def get_parameter_importance(self, experiment_id: str) -> dict:
        if self._experiment_repo:
            experiment = await self._experiment_repo.get_by_id(experiment_id)
            if experiment and len(experiment.trials) >= 5:
                # Simple variance-based importance estimation
                param_keys = list(experiment.parameter_space.keys())
                importance: dict[str, float] = {}

                for key in param_keys:
                    values = []
                    rewards = []
                    for trial in experiment.trials:
                        if key in trial.parameters and trial.reward:
                            values.append(trial.parameters[key])
                            rewards.append(trial.reward.total)

                    if len(values) >= 3:
                        # Simple correlation proxy
                        try:
                            mean_val = sum(values) / len(values)
                            mean_rew = sum(rewards) / len(rewards)
                            cov = sum((v - mean_val) * (r - mean_rew) for v, r in zip(values, rewards))
                            var_val = sum((v - mean_val) ** 2 for v in values)
                            importance[key] = abs(cov / var_val) if var_val > 0 else 0.0
                        except Exception:
                            importance[key] = 0.0
                    else:
                        importance[key] = 0.0

                # Normalize
                total = sum(importance.values())
                if total > 0:
                    importance = {k: v / total for k, v in importance.items()}

                return {"status": "computed", "importance": importance}

        return {"status": "insufficient_data", "importance": {}}

    async def compare_experiments(self, experiment_ids: list[str]) -> dict:
        results = {}
        for exp_id in experiment_ids:
            results[exp_id] = await self.get_experiment_results(exp_id)
        return results
