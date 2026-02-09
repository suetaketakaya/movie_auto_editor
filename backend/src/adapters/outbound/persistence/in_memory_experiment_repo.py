"""In-memory implementation of ExperimentRepositoryPort."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.src.core.entities.experiment import Experiment, Trial

logger = logging.getLogger(__name__)


class InMemoryExperimentRepo:
    """Thread-safe in-memory implementation of ExperimentRepositoryPort."""

    def __init__(self) -> None:
        self._store: dict[str, Experiment] = {}
        self._lock = asyncio.Lock()

    async def save(self, experiment: Experiment) -> Experiment:
        async with self._lock:
            self._store[experiment.id] = experiment
            logger.debug("Saved experiment %s in memory", experiment.id)
            return experiment

    async def get_by_id(self, experiment_id: str) -> Optional[Experiment]:
        return self._store.get(experiment_id)

    async def list_all(self) -> list[Experiment]:
        return list(self._store.values())

    async def add_trial(self, experiment_id: str, trial: Trial) -> None:
        async with self._lock:
            experiment = self._store.get(experiment_id)
            if experiment is None:
                logger.warning("Experiment %s not found for trial", experiment_id)
                return
            experiment.add_trial(trial)
            logger.debug("Added trial #%d to experiment %s", trial.trial_num, experiment_id)
