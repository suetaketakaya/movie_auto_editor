"""Project aggregate root - the main entity for the processing pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.timeline import Timeline
from backend.src.core.entities.video import Video


class ProjectStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Project:
    """Aggregate root for a video processing job.

    Replaces the legacy active_jobs[job_id] dict structure.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    filename: str = ""
    upload_path: str = ""
    input_video_path: str = ""
    output_dir: str = ""
    content_type: ContentType = ContentType.GENERAL
    config: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    status: ProjectStatus = ProjectStatus.UPLOADED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    video: Optional[Video] = None
    frame_analyses: list[FrameAnalysis] = field(default_factory=list)
    timeline: Optional[Timeline] = None
    output_paths: dict[str, str] = field(default_factory=dict)
    result: Optional[dict] = None
    engagement_prediction: Optional[dict] = None
    chapters: list[dict] = field(default_factory=list)
    multi_kills: list[dict] = field(default_factory=list)
    clutch_moments: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    error_message: Optional[str] = None
    progress: int = 0
    current_stage: str = ""

    def start_processing(self) -> None:
        self.status = ProjectStatus.PROCESSING
        self.progress = 0
        self.updated_at = datetime.utcnow()

    def complete(
        self,
        output_paths: Optional[dict[str, str]] = None,
        result: Optional[dict] = None,
    ) -> None:
        self.status = ProjectStatus.COMPLETED
        if output_paths is not None:
            self.output_paths = output_paths
        if result is not None:
            self.result = result
        self.progress = 100
        self.updated_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        self.status = ProjectStatus.FAILED
        self.error = error
        self.error_message = error
        self.progress = 0
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        self.status = ProjectStatus.CANCELLED
        self.error = "cancelled"
        self.error_message = "cancelled"
        self.updated_at = datetime.utcnow()

    def update_progress(self, stage: str, progress: int) -> None:
        self.current_stage = stage
        self.progress = progress
        self.updated_at = datetime.utcnow()

    def to_legacy_dict(self) -> dict:
        """Convert to legacy active_jobs dict format."""
        result: dict = {
            "id": self.id,
            "name": self.name,
            "filename": self.filename,
            "upload_path": self.upload_path,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "progress": self.progress,
        }
        if self.output_paths:
            result.update(self.output_paths)
        if self.engagement_prediction:
            result["engagement_prediction"] = self.engagement_prediction
        if self.chapters:
            result["chapters"] = self.chapters
        return result
