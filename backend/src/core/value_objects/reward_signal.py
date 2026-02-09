"""RewardSignal value object for reinforcement learning."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_WEIGHTS: dict[str, float] = {
    "retention": 0.30,
    "ctr": 0.20,
    "engagement": 0.15,
    "watch_time": 0.15,
    "llm_quality": 0.10,
    "diversity": 0.10,
}


@dataclass(frozen=True)
class RewardSignal:
    """Composite reward value combining multiple quality signals."""

    total: float
    components: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())

    @property
    def dominant_component(self) -> str | None:
        if not self.components:
            return None
        return max(self.components, key=self.components.get)  # type: ignore[arg-type]

    @property
    def is_positive(self) -> bool:
        return self.total > 0

    def reweight(self, new_weights: dict[str, float]) -> RewardSignal:
        total_w = sum(new_weights.values())
        if total_w == 0:
            return RewardSignal(total=0.0, components=self.components, weights=new_weights)
        normalized = {k: v / total_w for k, v in new_weights.items()}
        new_total = sum(normalized.get(k, 0) * self.components.get(k, 0) for k in normalized)
        return RewardSignal(total=new_total, components=self.components, weights=normalized)

    def without_component(self, name: str) -> RewardSignal:
        """Remove a component and renormalize weights (for ablation studies)."""
        new_components = {k: v for k, v in self.components.items() if k != name}
        new_weights = {k: v for k, v in self.weights.items() if k != name}
        total_w = sum(new_weights.values())
        if total_w > 0:
            new_weights = {k: v / total_w for k, v in new_weights.items()}
        new_total = sum(new_weights.get(k, 0) * new_components.get(k, 0) for k in new_weights)
        return RewardSignal(total=new_total, components=new_components, weights=new_weights)

    @classmethod
    def compute(cls, components: dict[str, float], weights: dict[str, float] | None = None) -> RewardSignal:
        w = weights or DEFAULT_WEIGHTS.copy()
        total_w = sum(w.values())
        if total_w == 0:
            return cls(total=0.0, components=components, weights=w)
        normalized = {k: v / total_w for k, v in w.items()}
        total = sum(normalized.get(k, 0) * components.get(k, 0) for k in normalized)
        return cls(total=total, components=components, weights=normalized)
