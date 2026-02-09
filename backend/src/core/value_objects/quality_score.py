"""QualityScore value object - bounded 0-100 score."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QualityScore:
    """Bounded quality score between 0 and 100."""

    value: float
    breakdown: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clamped = max(0.0, min(100.0, self.value))
        object.__setattr__(self, "value", clamped)

    @property
    def is_acceptable(self) -> bool:
        return self.value >= 70.0

    @property
    def grade(self) -> str:
        if self.value >= 90:
            return "A"
        if self.value >= 80:
            return "B"
        if self.value >= 70:
            return "C"
        if self.value >= 60:
            return "D"
        return "F"

    @classmethod
    def from_components(cls, weights: dict[str, float], scores: dict[str, float]) -> QualityScore:
        total_weight = sum(weights.values())
        if total_weight == 0:
            return cls(value=0.0)
        weighted_sum = sum(weights.get(k, 0) * scores.get(k, 0) for k in weights)
        return cls(value=weighted_sum / total_weight, breakdown=scores)

    def with_bonus(self, bonus: float, reason: str = "") -> QualityScore:
        new_breakdown = dict(self.breakdown)
        if reason:
            new_breakdown[reason] = bonus
        return QualityScore(value=self.value + bonus, breakdown=new_breakdown)

    @classmethod
    def zero(cls) -> QualityScore:
        return cls(value=0.0)

    @classmethod
    def perfect(cls) -> QualityScore:
        return cls(value=100.0)
