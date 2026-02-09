"""DTO for experiment configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExperimentConfig:
    n_initial_random: int = 10
    n_optimization_trials: int = 50
    kernel: str = "matern"
    acquisition: str = "thompson_sampling"
    reward_weights: dict = field(default_factory=lambda: {
        "retention": 0.30, "ctr": 0.20, "engagement": 0.15,
        "watch_time": 0.15, "llm_quality": 0.10, "diversity": 0.10,
    })
    parameter_space: Optional[dict] = None
