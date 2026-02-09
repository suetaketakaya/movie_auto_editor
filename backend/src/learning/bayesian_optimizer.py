"""
Bayesian optimization with Gaussian Processes and Thompson Sampling.
Matern kernel (ν=2.5) for smooth exploration of the parameter space.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from backend.src.learning.parameter_space import ParameterSpace

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of an optimization run."""
    best_params: dict[str, float]
    best_reward: float
    all_params: list[dict[str, float]]
    all_rewards: list[float]
    n_trials: int
    gp_uncertainty: list[float] = field(default_factory=list)


class BayesianOptimizer:
    """GP-based Bayesian optimization with Thompson Sampling.

    Features:
        - Matern(2.5) + ConstantKernel
        - Thompson Sampling acquisition
        - Sobol initialization (10 points)
        - 2000 candidate points for acquisition
    """

    def __init__(
        self,
        parameter_space: Optional[ParameterSpace] = None,
        n_initial: int = 10,
        n_candidates: int = 2000,
        random_state: int = 42,
    ):
        self.space = parameter_space or ParameterSpace()
        self.n_initial = n_initial
        self.n_candidates = n_candidates
        self.rng = np.random.default_rng(random_state)

        self._X: list[np.ndarray] = []
        self._y: list[float] = []
        self._gp = None
        self._uncertainties: list[float] = []

    @property
    def n_observations(self) -> int:
        return len(self._y)

    def suggest(self) -> dict[str, float]:
        """Suggest next parameters to try."""
        if self.n_observations < self.n_initial:
            # Initial exploration with Sobol
            samples = self.space.sobol_samples(self.n_initial)
            if self.n_observations < len(samples):
                return samples[self.n_observations]
            return self.space.random_sample(self.rng)

        # Fit GP and use Thompson Sampling
        self._fit_gp()
        return self._thompson_sampling()

    def observe(self, params: dict[str, float], reward: float) -> None:
        """Record an observation."""
        x = np.array(self.space.dict_to_array(params))
        self._X.append(x)
        self._y.append(reward)
        logger.info(
            "Observation %d: reward=%.4f",
            self.n_observations, reward,
        )

    def get_best(self) -> tuple[dict[str, float], float]:
        """Return best parameters and reward seen so far."""
        if not self._y:
            return {}, 0.0
        best_idx = int(np.argmax(self._y))
        return self.space.array_to_dict(self._X[best_idx].tolist()), self._y[best_idx]

    def get_result(self) -> OptimizationResult:
        """Get full optimization result."""
        best_params, best_reward = self.get_best()
        return OptimizationResult(
            best_params=best_params,
            best_reward=best_reward,
            all_params=[self.space.array_to_dict(x.tolist()) for x in self._X],
            all_rewards=list(self._y),
            n_trials=self.n_observations,
            gp_uncertainty=list(self._uncertainties),
        )

    def predict(self, params: dict[str, float]) -> tuple[float, float]:
        """Predict mean and std for given parameters."""
        if self._gp is None:
            self._fit_gp()
        x = np.array(self.space.dict_to_array(params)).reshape(1, -1)
        mean, std = self._gp.predict(x, return_std=True)
        return float(mean[0]), float(std[0])

    def get_uncertainty_surface(self, resolution: int = 50) -> dict:
        """Get GP uncertainty for visualization (2D slices)."""
        if self._gp is None:
            return {}

        lows, highs = self.space.to_array_bounds()
        # Default slice: first two parameters
        x0 = np.linspace(lows[0], highs[0], resolution)
        x1 = np.linspace(lows[1], highs[1], resolution)
        xx0, xx1 = np.meshgrid(x0, x1)

        # Fix other dimensions at midpoint
        mid = (lows + highs) / 2
        grid = np.tile(mid, (resolution * resolution, 1))
        grid[:, 0] = xx0.ravel()
        grid[:, 1] = xx1.ravel()

        _, std = self._gp.predict(grid, return_std=True)
        return {
            "x0": x0.tolist(),
            "x1": xx1.tolist(),
            "uncertainty": std.reshape(resolution, resolution).tolist(),
            "param_names": [self.space.names[0], self.space.names[1]],
        }

    def _fit_gp(self) -> None:
        """Fit Gaussian Process to observations."""
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import Matern, ConstantKernel
        except ImportError:
            logger.warning("scikit-learn not available, using fallback")
            self._gp = _FallbackGP(self._X, self._y)
            return

        X = np.array(self._X)
        y = np.array(self._y)

        # Normalize
        self._X_mean = X.mean(axis=0)
        self._X_std = X.std(axis=0) + 1e-8
        self._y_mean = y.mean()
        self._y_std = y.std() + 1e-8

        X_norm = (X - self._X_mean) / self._X_std
        y_norm = (y - self._y_mean) / self._y_std

        kernel = ConstantKernel(1.0) * Matern(nu=2.5)
        self._gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=5,
            normalize_y=True,
            random_state=42,
        )
        self._gp.fit(X_norm, y_norm)

        # Track uncertainty
        _, std = self._gp.predict(X_norm, return_std=True)
        self._uncertainties.append(float(std.mean()))

    def _thompson_sampling(self) -> dict[str, float]:
        """Thompson Sampling acquisition: sample from GP posterior."""
        lows, highs = self.space.to_array_bounds()
        candidates = self.rng.uniform(
            lows, highs, size=(self.n_candidates, self.space.dimension)
        )

        # Normalize candidates
        X_norm = (candidates - self._X_mean) / self._X_std

        # Sample from posterior
        mean, std = self._gp.predict(X_norm, return_std=True)
        samples = self.rng.normal(mean, std)

        best_idx = int(np.argmax(samples))
        return self.space.array_to_dict(candidates[best_idx].tolist())


class _FallbackGP:
    """Simple fallback when sklearn is not available."""

    def __init__(self, X, y):
        self._X = np.array(X) if X else np.empty((0, 1))
        self._y = np.array(y) if y else np.empty(0)

    def predict(self, X, return_std=False):
        mean = np.full(len(X), self._y.mean() if len(self._y) > 0 else 0.0)
        if return_std:
            std = np.full(len(X), self._y.std() if len(self._y) > 1 else 1.0)
            return mean, std
        return mean
