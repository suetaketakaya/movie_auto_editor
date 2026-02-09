"""Experiment and Trial entities for RL-based optimization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.src.core.entities.content_type import ContentType
from backend.src.core.value_objects.reward_signal import RewardSignal


class ExperimentStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Trial:
    """A single trial within an experiment."""

    trial_num: int
    parameters: dict = field(default_factory=dict)
    reward: Optional[RewardSignal] = None
    sub_metrics: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Experiment:
    """An optimization experiment with multiple trials."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    content_type: ContentType = ContentType.GENERAL
    parameter_space: dict = field(default_factory=dict)
    status: ExperimentStatus = ExperimentStatus.CREATED
    trials: list[Trial] = field(default_factory=list)
    best_trial: Optional[Trial] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_trial(self, trial: Trial) -> None:
        self.trials.append(trial)
        if self.best_trial is None or (
            trial.reward is not None
            and self.best_trial.reward is not None
            and trial.reward.total > self.best_trial.reward.total
        ):
            self.best_trial = trial
        self.updated_at = datetime.utcnow()
