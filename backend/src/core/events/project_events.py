"""Domain events related to project processing."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ProjectCreated:
    project_id: str
    filename: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ProcessingStarted:
    project_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ProcessingStageChanged:
    project_id: str
    stage: str
    progress: int
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ProcessingCompleted:
    project_id: str
    output_paths: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ProcessingFailed:
    project_id: str
    error: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
