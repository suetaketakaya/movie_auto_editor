"""
Parameter space definition for Bayesian optimization.
11-dimensional search space for video editing parameters.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParameterBound:
    """Single parameter with bounds and metadata."""
    name: str
    low: float
    high: float
    description: str = ""
    parameter_type: str = "continuous"  # continuous, integer, categorical
    log_scale: bool = False


# Default 11-dimensional parameter space
DEFAULT_PARAMETER_SPACE: list[ParameterBound] = [
    ParameterBound("clip_min_length", 2.0, 15.0, "Minimum clip length (seconds)"),
    ParameterBound("clip_max_length", 10.0, 45.0, "Maximum clip length (seconds)"),
    ParameterBound("target_duration", 60.0, 600.0, "Target video duration (seconds)"),
    ParameterBound("hook_duration", 1.0, 5.0, "Hook intro duration (seconds)"),
    ParameterBound("pacing_variation", 0.0, 1.0, "Pacing variation degree"),
    ParameterBound("color_saturation", 0.5, 1.5, "Color saturation"),
    ParameterBound("color_contrast", 0.8, 1.5, "Color contrast"),
    ParameterBound("audio_music_ratio", 0.0, 0.5, "BGM volume ratio"),
    ParameterBound("transition_duration", 0.1, 1.5, "Transition duration (seconds)"),
    ParameterBound("text_overlay_freq", 0.0, 1.0, "Text overlay frequency"),
    ParameterBound("excitement_threshold", 10.0, 40.0, "Excitement threshold"),
]


class ParameterSpace:
    """Manages the parameter space for optimization."""

    def __init__(self, parameters: list[ParameterBound] | None = None):
        self.parameters = parameters or DEFAULT_PARAMETER_SPACE
        self._param_map = {p.name: p for p in self.parameters}

    @property
    def dimension(self) -> int:
        return len(self.parameters)

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.parameters]

    @property
    def bounds(self) -> list[tuple[float, float]]:
        return [(p.low, p.high) for p in self.parameters]

    def get_bound(self, name: str) -> ParameterBound:
        return self._param_map[name]

    def to_array_bounds(self):
        """Return bounds as numpy-compatible arrays."""
        import numpy as np
        lows = np.array([p.low for p in self.parameters])
        highs = np.array([p.high for p in self.parameters])
        return lows, highs

    def dict_to_array(self, params: dict) -> list[float]:
        """Convert parameter dict to ordered array."""
        return [params[p.name] for p in self.parameters]

    def array_to_dict(self, values: list[float]) -> dict[str, float]:
        """Convert ordered array to parameter dict."""
        return {p.name: v for p, v in zip(self.parameters, values)}

    def random_sample(self, rng=None) -> dict[str, float]:
        """Generate a random sample within bounds."""
        import numpy as np
        rng = rng or np.random.default_rng()
        return {
            p.name: float(rng.uniform(p.low, p.high))
            for p in self.parameters
        }

    def sobol_samples(self, n: int) -> list[dict[str, float]]:
        """Generate Sobol quasi-random samples for initial exploration."""
        import numpy as np
        try:
            from scipy.stats.qmc import Sobol
            sampler = Sobol(d=self.dimension, scramble=True)
            raw = sampler.random(n)
        except ImportError:
            raw = np.random.rand(n, self.dimension)

        lows, highs = self.to_array_bounds()
        scaled = raw * (highs - lows) + lows
        return [self.array_to_dict(row.tolist()) for row in scaled]
