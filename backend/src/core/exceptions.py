"""Custom exception hierarchy for ClipMontage."""
from __future__ import annotations


class ClipMontageError(Exception):
    """Base exception for all ClipMontage errors."""


class ProjectNotFoundError(ClipMontageError):
    """Raised when a project cannot be found."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project not found: {project_id}")


class ProcessingError(ClipMontageError):
    """Raised when video processing fails."""


class UploadValidationError(ClipMontageError):
    """Raised when an uploaded file fails validation."""


class AIAnalysisError(ClipMontageError):
    """Raised when AI analysis fails after all retries."""


class FFmpegError(ClipMontageError):
    """Raised when an FFmpeg operation fails."""
