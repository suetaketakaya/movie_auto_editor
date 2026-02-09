"""
Composite reward function for RL-based optimization.
Wraps the domain RewardCalculator with learning-specific functionality.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.src.core.services.reward_calculator import RewardCalculator
from backend.src.core.value_objects.reward_signal import RewardSignal

logger = logging.getLogger(__name__)


class RewardFunction:
    """Learning-oriented reward function with normalization and history tracking.

    reward = Σ w_i × R_i

    Default components:
        retention=0.30, ctr=0.20, engagement=0.15,
        watch_time=0.15, llm_quality=0.10, diversity=0.10
    """

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self._calculator = RewardCalculator(weights=weights)
        self._history: list[RewardSignal] = []

    @property
    def weights(self) -> dict[str, float]:
        return self._calculator.weights

    def compute(self, metrics: dict[str, float]) -> RewardSignal:
        """Compute reward from 0-1 normalized metrics."""
        signal = self._calculator.calculate(metrics)
        self._history.append(signal)
        return signal

    def compute_from_results(self, clips, analyses, quality_score, target_duration=180.0) -> RewardSignal:
        """Compute from actual processing results."""
        signal = self._calculator.calculate_from_clips(
            clips, analyses, quality_score, target_duration
        )
        self._history.append(signal)
        return signal

    def get_history(self) -> list[dict]:
        """Return reward history as dicts."""
        return [
            {"total": s.total, "components": s.components}
            for s in self._history
        ]

    def get_running_best(self) -> float:
        """Get best reward seen so far."""
        if not self._history:
            return 0.0
        return max(s.total for s in self._history)

    def get_cumulative_regret(self, oracle_reward: float = 1.0) -> list[float]:
        """Compute cumulative regret vs oracle."""
        regret = []
        cumulative = 0.0
        for s in self._history:
            cumulative += oracle_reward - s.total
            regret.append(cumulative)
        return regret

    def ablate(self, component_name: str) -> RewardFunction:
        """Create ablated version (one component removed, weights renormalized)."""
        ablated_calc = self._calculator.ablate(component_name)
        return RewardFunction(weights=ablated_calc.weights)
