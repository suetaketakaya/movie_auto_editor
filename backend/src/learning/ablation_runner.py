"""
Ablation study automation.
Removes each reward component individually and re-optimizes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.src.learning.bayesian_optimizer import BayesianOptimizer
from backend.src.learning.experiment_tracker import ExperimentTracker
from backend.src.learning.parameter_space import ParameterSpace
from backend.src.learning.reward_function import RewardFunction

logger = logging.getLogger(__name__)


@dataclass
class AblationResult:
    """Result of a single ablation."""
    component_removed: str
    baseline_reward: float
    ablated_reward: float
    delta: float
    ablated_best_params: dict[str, float] = field(default_factory=dict)


class AblationRunner:
    """Runs ablation studies on reward function components.

    For each of the 6 reward components, removes it, renormalizes
    remaining weights, and re-optimizes to measure contribution.
    """

    def __init__(
        self,
        reward_function: RewardFunction,
        evaluate_fn: Callable[[dict[str, float]], dict[str, float]],
        parameter_space: Optional[ParameterSpace] = None,
        tracker: Optional[ExperimentTracker] = None,
        n_trials_per_ablation: int = 20,
    ):
        self._reward = reward_function
        self._evaluate_fn = evaluate_fn
        self._space = parameter_space or ParameterSpace()
        self._tracker = tracker
        self._n_trials = n_trials_per_ablation

    def run_full_ablation(self, baseline_reward: float) -> list[AblationResult]:
        """Run ablation for all reward components."""
        components = list(self._reward.weights.keys())
        results: list[AblationResult] = []

        for component in components:
            logger.info("Ablation: removing %s", component)
            result = self._ablate_component(component, baseline_reward)
            results.append(result)

            if self._tracker:
                self._tracker.log_ablation(
                    name=f"ablation_{component}",
                    removed_component=component,
                    baseline_reward=baseline_reward,
                    ablated_reward=result.ablated_reward,
                )

        # Sort by delta (most important first)
        results.sort(key=lambda r: r.delta, reverse=True)
        return results

    def _ablate_component(
        self, component_name: str, baseline_reward: float
    ) -> AblationResult:
        """Ablate a single component and re-optimize."""
        ablated_reward_fn = self._reward.ablate(component_name)
        optimizer = BayesianOptimizer(
            parameter_space=self._space,
            n_initial=5,
            n_candidates=1000,
        )

        best_reward = 0.0
        best_params = {}

        for i in range(self._n_trials):
            params = optimizer.suggest()
            metrics = self._evaluate_fn(params)
            signal = ablated_reward_fn.compute(metrics)
            optimizer.observe(params, signal.total)

            if signal.total > best_reward:
                best_reward = signal.total
                best_params = params

        delta = baseline_reward - best_reward
        return AblationResult(
            component_removed=component_name,
            baseline_reward=baseline_reward,
            ablated_reward=best_reward,
            delta=delta,
            ablated_best_params=best_params,
        )

    def format_table(self, results: list[AblationResult]) -> str:
        """Format ablation results as a text table."""
        lines = [
            f"{'Component':<20} {'Baseline':>10} {'Ablated':>10} {'Δ':>10} {'Impact':>10}",
            "-" * 62,
        ]
        for r in results:
            pct = (r.delta / r.baseline_reward * 100) if r.baseline_reward > 0 else 0
            lines.append(
                f"{r.component_removed:<20} {r.baseline_reward:>10.4f} "
                f"{r.ablated_reward:>10.4f} {r.delta:>+10.4f} {pct:>9.1f}%"
            )
        return "\n".join(lines)
