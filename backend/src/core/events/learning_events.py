"""Domain events related to RL experiments."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ExperimentCreated:
    experiment_id: str
    name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class TrialCompleted:
    experiment_id: str
    trial_num: int
    reward: float
    parameters: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class OptimizationCompleted:
    experiment_id: str
    best_reward: float
    best_parameters: dict
    total_trials: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
