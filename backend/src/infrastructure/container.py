"""
Dependency injection container using dependency-injector.
Wires together ports and adapters based on configuration.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.src.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class ApplicationContainer:
    """Simplified container that builds concrete instances from settings.

    Usage::

        container = ApplicationContainer(settings)
        service = container.process_video_service()
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._cache: dict[str, object] = {}

    def _get_or_create(self, key: str, factory):
        if key not in self._cache:
            self._cache[key] = factory(self.settings)
        return self._cache[key]

    # ── Lazy factory helpers ──────────────────────────────────────

    @staticmethod
    def _build_user_auth(settings: Settings):
        if settings.firebase.enabled:
            from backend.src.adapters.outbound.firebase.firebase_auth import FirebaseAuthAdapter
            return FirebaseAuthAdapter(
                credentials_path=settings.firebase.credentials_path,
                project_id=settings.firebase.project_id,
            )
        else:
            from backend.src.adapters.outbound.firebase.noop_auth import NoopAuthAdapter
            return NoopAuthAdapter()

    @staticmethod
    def _build_video_editor(settings: Settings):
        from backend.src.adapters.outbound.ffmpeg.ffmpeg_video_editor import FFmpegVideoEditor
        return FFmpegVideoEditor(config=settings.to_legacy_dict())

    @staticmethod
    def _build_effects(settings: Settings):
        from backend.src.adapters.outbound.ffmpeg.ffmpeg_effects import FFmpegVisualEffects
        return FFmpegVisualEffects(config=settings.to_legacy_dict())

    @staticmethod
    def _build_text_overlay(settings: Settings):
        from backend.src.adapters.outbound.ffmpeg.ffmpeg_text_overlay import FFmpegTextOverlay
        return FFmpegTextOverlay(config=settings.to_legacy_dict())

    @staticmethod
    def _build_audio(settings: Settings):
        from backend.src.adapters.outbound.ffmpeg.ffmpeg_audio import FFmpegAudioProcessor
        return FFmpegAudioProcessor(config=settings.to_legacy_dict())

    @staticmethod
    def _build_encoding(settings: Settings):
        from backend.src.adapters.outbound.ffmpeg.ffmpeg_encoding import FFmpegEncoder
        return FFmpegEncoder(config=settings.to_legacy_dict())

    @staticmethod
    def _build_vision(settings: Settings):
        from backend.src.adapters.outbound.ai.ollama_vision import OllamaVisionAdapter
        return OllamaVisionAdapter(config=settings.to_legacy_dict())

    @staticmethod
    def _build_frame_extraction(settings: Settings):
        from backend.src.adapters.outbound.media.opencv_frames import OpenCVFrameExtractor
        return OpenCVFrameExtractor(config=settings.to_legacy_dict())

    @staticmethod
    def _build_project_repository(settings: Settings):
        if settings.persistence_backend == "postgres":
            from backend.src.adapters.outbound.persistence.postgres_project_repo import PostgresProjectRepository
            from backend.src.infrastructure.database import get_async_session_factory
            session_factory = get_async_session_factory(settings.database.url)
            return PostgresProjectRepository(session_factory)
        else:
            from backend.src.adapters.outbound.persistence.in_memory_project_repo import InMemoryProjectRepository
            return InMemoryProjectRepository()

    @staticmethod
    def _build_experiment_repository(settings: Settings):
        if settings.persistence_backend == "postgres":
            from backend.src.adapters.outbound.persistence.postgres_experiment_repo import PostgresExperimentRepository
            from backend.src.infrastructure.database import get_async_session_factory
            session_factory = get_async_session_factory(settings.database.url)
            return PostgresExperimentRepository(session_factory)
        else:
            from backend.src.adapters.outbound.persistence.in_memory_experiment_repo import InMemoryExperimentRepo
            return InMemoryExperimentRepo()

    @staticmethod
    def _build_file_storage(settings: Settings):
        from backend.src.adapters.outbound.persistence.local_file_storage import LocalFileStorage
        return LocalFileStorage(base_dir=settings.storage.media_root)

    @staticmethod
    def _build_task_queue(settings: Settings):
        if settings.app_env == "production":
            try:
                from backend.src.adapters.outbound.queue.celery_queue import CeleryTaskQueue
                return CeleryTaskQueue(broker_url=settings.celery.broker_url)
            except ImportError:
                logger.warning("Celery not installed, falling back to in-process queue")
        from backend.src.adapters.outbound.queue.in_process_queue import InProcessTaskQueue
        return InProcessTaskQueue()

    @staticmethod
    def _build_notification(settings: Settings):
        from backend.src.adapters.outbound.external.websocket_notifier import WebSocketNotifier
        return WebSocketNotifier()

    @staticmethod
    def _build_metrics_store(settings: Settings):
        if settings.mlflow.enabled:
            from backend.src.adapters.outbound.metrics.mlflow_store import MLflowMetricsStore
            return MLflowMetricsStore(tracking_uri=settings.mlflow.tracking_uri)
        else:
            from backend.src.adapters.outbound.metrics.file_metrics_store import FileMetricsStore
            return FileMetricsStore(base_dir=settings.storage.media_root)

    @staticmethod
    def _build_llm_reasoning(settings: Settings):
        from backend.src.adapters.outbound.ai.langchain_reasoning import LangChainReasoningAdapter
        return LangChainReasoningAdapter(
            base_url=settings.ollama.base_url,
            model=settings.ollama.thinking_model,
            timeout=settings.ollama.timeout,
        )

    @staticmethod
    def _build_thumbnail(settings: Settings):
        from backend.src.adapters.outbound.media.pil_thumbnail import PILThumbnailAdapter
        return PILThumbnailAdapter(config=settings.thumbnail.model_dump())

    @staticmethod
    def _build_youtube_api(settings: Settings):
        from backend.src.adapters.outbound.external.youtube_data_api import YouTubeDataAPIAdapter
        return YouTubeDataAPIAdapter()

    # ── Port accessors ─────────────────────────────────────────────

    def user_auth(self):
        return self._get_or_create("user_auth", self._build_user_auth)

    def video_editor(self):
        return self._get_or_create("video_editor", self._build_video_editor)

    def effects(self):
        return self._get_or_create("effects", self._build_effects)

    def text_overlay(self):
        return self._get_or_create("text_overlay", self._build_text_overlay)

    def audio(self):
        return self._get_or_create("audio", self._build_audio)

    def encoding(self):
        return self._get_or_create("encoding", self._build_encoding)

    def vision(self):
        return self._get_or_create("vision", self._build_vision)

    def frame_extraction(self):
        return self._get_or_create("frame_extraction", self._build_frame_extraction)

    def project_repository(self):
        return self._get_or_create("project_repository", self._build_project_repository)

    def experiment_repository(self):
        return self._get_or_create("experiment_repository", self._build_experiment_repository)

    def file_storage(self):
        return self._get_or_create("file_storage", self._build_file_storage)

    def task_queue(self):
        return self._get_or_create("task_queue", self._build_task_queue)

    def notification(self):
        return self._get_or_create("notification", self._build_notification)

    def metrics_store(self):
        return self._get_or_create("metrics_store", self._build_metrics_store)

    def llm_reasoning(self):
        return self._get_or_create("llm_reasoning", self._build_llm_reasoning)

    def thumbnail(self):
        return self._get_or_create("thumbnail", self._build_thumbnail)

    def youtube_api(self):
        return self._get_or_create("youtube_api", self._build_youtube_api)

    # ── Application services ───────────────────────────────────────

    def process_video_service(self):
        from backend.src.application.process_video_service import ProcessVideoService
        return ProcessVideoService(
            vision=self.vision(),
            editor=self.video_editor(),
            audio=self.audio(),
            effects=self.effects(),
            text_overlay=self.text_overlay(),
            frame_extraction=self.frame_extraction(),
            repository=self.project_repository(),
            notifier=self.notification(),
        )

    def project_service(self):
        from backend.src.application.project_service import ProjectService
        return ProjectService(
            repository=self.project_repository(),
            file_storage=self.file_storage(),
            task_queue=self.task_queue(),
        )

    def experiment_service(self):
        from backend.src.application.experiment_service import ExperimentService
        return ExperimentService(
            metrics_store=self.metrics_store(),
            project_repository=self.project_repository(),
            experiment_repo=self.experiment_repository(),
        )
