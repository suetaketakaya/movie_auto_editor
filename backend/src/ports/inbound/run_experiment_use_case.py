"""Inbound port for experiment execution."""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, runtime_checkable
if TYPE_CHECKING:
    from backend.src.application.dto.experiment_config import ExperimentConfig
    from backend.src.core.entities.content_type import ContentType
    from backend.src.core.entities.experiment import Experiment, Trial


@runtime_checkable
class RunExperimentUseCase(Protocol):
    async def create_experiment(self, name: str, content_type: ContentType, config: ExperimentConfig) -> Experiment: ...
    async def run_trial(self, experiment_id: str, parameters: dict) -> Trial: ...
    async def run_optimization(self, experiment_id: str, n_trials: int = 50) -> Experiment: ...
    async def run_ablation(self, experiment_id: str) -> dict: ...
