"""DTO for video processing requests."""
from __future__ import annotations
from dataclasses import dataclass, field
from backend.src.core.entities.content_type import ContentType


@dataclass
class ProcessRequest:
    project_id: str
    video_path: str = ""
    project_name: str = ""
    input_video_path: str = ""
    output_dir: str = ""
    content_type: ContentType = ContentType.FPS_MONTAGE
    target_duration: float = 180.0
    config: dict = field(default_factory=dict)
    enable_effects: bool = True
    enable_text_overlay: bool = True
    enable_audio_processing: bool = True
    enable_thumbnails: bool = True
    enable_short_videos: bool = True
    enable_super_resolution: bool = False
    enable_gpu_encoding: bool = True
    enable_subtitles: bool = False
    custom_config: dict = field(default_factory=dict)
