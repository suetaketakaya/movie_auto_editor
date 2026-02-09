"""TimeRange value object representing a time interval in a video."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeRange:
    """Immutable time range with start and end in seconds."""

    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            object.__setattr__(self, "start_seconds", 0.0)
        if self.end_seconds <= self.start_seconds:
            raise ValueError(
                f"end_seconds ({self.end_seconds}) must be greater than start_seconds ({self.start_seconds})"
            )

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds

    @property
    def midpoint(self) -> float:
        return (self.start_seconds + self.end_seconds) / 2

    def overlaps(self, other: TimeRange) -> bool:
        return self.start_seconds < other.end_seconds and other.start_seconds < self.end_seconds

    def contains(self, timestamp: float) -> bool:
        return self.start_seconds <= timestamp <= self.end_seconds

    def merge(self, other: TimeRange) -> TimeRange:
        if not self.overlaps(other):
            raise ValueError("Cannot merge non-overlapping time ranges")
        return TimeRange(
            start_seconds=min(self.start_seconds, other.start_seconds),
            end_seconds=max(self.end_seconds, other.end_seconds),
        )

    def extend(self, before: float = 0.0, after: float = 0.0) -> TimeRange:
        return TimeRange(
            start_seconds=max(0.0, self.start_seconds - before),
            end_seconds=self.end_seconds + after,
        )

    def split(self, at_seconds: float) -> tuple[TimeRange, TimeRange]:
        if not self.contains(at_seconds):
            raise ValueError(f"Split point {at_seconds} is outside the range")
        return (
            TimeRange(self.start_seconds, at_seconds),
            TimeRange(at_seconds, self.end_seconds),
        )
