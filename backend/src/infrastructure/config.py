"""
ClipMontage configuration using Pydantic Settings.
Maps all settings from the legacy config.yaml with environment variable overrides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load .env before any BaseSettings subclass reads env vars
load_dotenv()


class OllamaSettings(BaseSettings):
    base_url: str = "http://localhost:11434"
    vision_model: str = "qwen2-vl:7b"
    thinking_model: str = "qwen2-vl:7b"
    timeout: int = 240
    use_llamacpp: bool = False

    model_config = {"env_prefix": "OLLAMA_"}


class MultiModelSettings(BaseSettings):
    enable: bool = True
    strategy: str = "confidence"
    models: list[str] = Field(default_factory=lambda: ["qwen2-vl:7b", "llama3.2-vision", "llava:13b"])
    confidence_threshold: float = 0.7
    parallel_processing: bool = True


class VideoSettings(BaseSettings):
    input_dir: str = "D:/uploads"
    output_dir: str = "./output"
    frames_dir: str = "./frames"
    sample_interval: int = 2


class FrameExtractionSettings(BaseSettings):
    interval_seconds: int = 2
    quality: int = 95
    max_frames: int = 2000


class AudioSettings(BaseSettings):
    enable: bool = True
    model: str = "base"
    trigger_keywords: list[str] = Field(default_factory=lambda: ["gunshot", "kill", "streak"])
    intensity_window: int = 5


class AIAnalysisSettings(BaseSettings):
    detect_kill_log: bool = True
    detect_match_status: bool = True
    detect_action_intensity: bool = True
    confidence_threshold: float = 0.7


class ExportSettings(BaseSettings):
    codec: str = "libx264"
    crf: int = 15
    preset: str = "slow"
    audio_bitrate: str = "320k"
    maintain_fps: bool = True
    maintain_resolution: bool = True


class CropSettings(BaseSettings):
    enable: bool = False
    aspect_ratio: str = "9:16"
    position: str = "center"


class WebSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_size_mb: int = 20000
    allowed_extensions: list[str] = Field(default_factory=lambda: [".mp4", ".mkv", ".avi", ".mov"])


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    file: str = "./logs/app.log"

    model_config = {"env_prefix": "LOG_"}


class TransitionSettings(BaseSettings):
    enable: bool = True
    type: str = "fade"
    duration: float = 0.5


class SlowMotionSettings(BaseSettings):
    enable: bool = True
    speed: float = 0.5
    apply_to_kills: bool = True


class ZoomSettings(BaseSettings):
    enable: bool = False
    factor: float = 1.5


class ColorGradingSettings(BaseSettings):
    enable: bool = True
    preset: str = "cinematic"


class VignetteSettings(BaseSettings):
    enable: bool = True
    intensity: float = 0.3


class EffectsSettings(BaseSettings):
    enable: bool = True
    transition: TransitionSettings = Field(default_factory=TransitionSettings)
    slow_motion: SlowMotionSettings = Field(default_factory=SlowMotionSettings)
    zoom: ZoomSettings = Field(default_factory=ZoomSettings)
    color_grading: ColorGradingSettings = Field(default_factory=ColorGradingSettings)
    vignette: VignetteSettings = Field(default_factory=VignetteSettings)


class KillCounterSettings(BaseSettings):
    enable: bool = True
    font_size: int = 48
    color: str = "white"
    position: str = "top_center"


class KillPopupsSettings(BaseSettings):
    enable: bool = True
    show_double_kill: bool = True
    show_triple_kill: bool = True
    show_quad_kill: bool = True
    show_ace: bool = True


class TextOverlaySettings(BaseSettings):
    enable: bool = True
    kill_counter: KillCounterSettings = Field(default_factory=KillCounterSettings)
    kill_popups: KillPopupsSettings = Field(default_factory=KillPopupsSettings)
    timestamp_enable: bool = False
    custom_text_enable: bool = False
    custom_text: str = ""


class BackgroundMusicSettings(BaseSettings):
    enable: bool = True
    music_path: str = ""
    video_volume: float = 0.7
    music_volume: float = 0.3


class NormalizationSettings(BaseSettings):
    enable: bool = True
    target_level: str = "-16dB"


class AudioEnhancementSettings(BaseSettings):
    enable: bool = True
    enhance_gunshots: bool = True


class FadeSettings(BaseSettings):
    enable: bool = True
    fade_in: float = 1.0
    fade_out: float = 1.0


class AudioProcessingSettings(BaseSettings):
    enable: bool = True
    background_music: BackgroundMusicSettings = Field(default_factory=BackgroundMusicSettings)
    normalization: NormalizationSettings = Field(default_factory=NormalizationSettings)
    enhancement: AudioEnhancementSettings = Field(default_factory=AudioEnhancementSettings)
    bass_boost_enable: bool = False
    bass_boost_gain: int = 5
    fade: FadeSettings = Field(default_factory=FadeSettings)


class CompositionSettings(BaseSettings):
    enable: bool = True
    target_duration: float = 180.0
    min_clip_length: float = 3.0
    max_clip_length: float = 15.0
    optimal_pace: float = 5.0
    sort_by_score: bool = True
    optimize_pacing: bool = True
    create_hook: bool = True


class ThumbnailYouTubeSettings(BaseSettings):
    enable: bool = True
    add_title: bool = True
    add_kill_count: bool = True


class ShortVideoSettings(BaseSettings):
    enable: bool = True
    format: str = "9:16"
    crop_position: str = "center"
    platforms: list[str] = Field(default_factory=lambda: ["youtube_shorts", "instagram_reel", "tiktok"])


class ThumbnailSettings(BaseSettings):
    enable: bool = True
    youtube: ThumbnailYouTubeSettings = Field(default_factory=ThumbnailYouTubeSettings)
    short_video: ShortVideoSettings = Field(default_factory=ShortVideoSettings)
    intro_path: str = ""
    outro_path: str = ""


class AdvancedAnalysisSettings(BaseSettings):
    enable: bool = True
    detect_multi_kills: bool = True
    multi_kill_window: float = 10.0
    detect_clutch: bool = True
    analyze_momentum: bool = True
    suggest_highlights: bool = True
    calculate_quality_score: bool = True


class SuperResolutionSettings(BaseSettings):
    enable: bool = False
    scale: int = 2
    model: str = "realesrgan-x4plus"
    enhance_faces: bool = True
    denoise_before_upscale: bool = True


class DenoiseSettings(BaseSettings):
    enable: bool = True
    strength: str = "medium"


class SharpenSettings(BaseSettings):
    enable: bool = True
    amount: float = 1.0


class LUTSettings(BaseSettings):
    enable: bool = True
    preset: str = "cinematic"
    custom_lut_file: str = ""


class GrainSettings(BaseSettings):
    enable: bool = False
    strength: float = 0.3


class VideoEnhancerSettings(BaseSettings):
    enable: bool = True
    denoise: DenoiseSettings = Field(default_factory=DenoiseSettings)
    stabilize_enable: bool = False
    stabilize_smoothing: int = 10
    sharpen: SharpenSettings = Field(default_factory=SharpenSettings)
    lut: LUTSettings = Field(default_factory=LUTSettings)
    grain: GrainSettings = Field(default_factory=GrainSettings)
    auto_levels: bool = False


class AudioEnhancerSettings(BaseSettings):
    enable: bool = True
    remove_noise: bool = True
    enhance_voice_clarity: bool = True
    voice_eq_preset: str = "gaming"


class SubtitleGeneratorSettings(BaseSettings):
    enable: bool = False
    model: str = "base"
    language: str = "ja"
    burn_into_video: bool = True
    font_size: int = 24
    font_color: str = "white"
    outline_color: str = "black"


class SmartCropperSettings(BaseSettings):
    enable: bool = True
    tracking_mode: str = "center"
    output_9_16: bool = True
    padding: int = 10


class GPUEncoderSettings(BaseSettings):
    enable: bool = True
    auto_detect: bool = True
    codec: str = "h264"
    quality: str = "high"
    preset: str = "p4"


class ThumbnailABTesterSettings(BaseSettings):
    enable: bool = True
    generate_variants: int = 5
    styles: list[str] = Field(
        default_factory=lambda: ["simple", "bold", "minimal", "dramatic", "bright"]
    )


class EngagementPredictorSettings(BaseSettings):
    enable: bool = True
    predict_retention: bool = True
    predict_ctr: bool = True
    suggest_improvements: bool = True


class ChapterGeneratorSettings(BaseSettings):
    enable: bool = True
    export_youtube_format: bool = True
    min_chapter_length: int = 30


class FirebaseSettings(BaseSettings):
    enabled: bool = False
    credentials_path: str = ""
    project_id: str = ""
    api_key: str = ""
    auth_domain: str = ""

    model_config = {"env_prefix": "FIREBASE_"}


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://clipmontage:clipmontage@localhost:5432/clipmontage"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    model_config = {"env_prefix": "DATABASE_"}


class RedisSettings(BaseSettings):
    url: str = "redis://localhost:6379/0"

    model_config = {"env_prefix": "REDIS_"}


class CelerySettings(BaseSettings):
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"

    model_config = {"env_prefix": "CELERY_"}


class MLflowSettings(BaseSettings):
    enabled: bool = False
    tracking_uri: str = "http://localhost:5000"

    model_config = {"env_prefix": "MLFLOW_"}


class StorageSettings(BaseSettings):
    media_root: str = "./media"
    upload_dir: str = "./media/uploads"
    output_dir: str = "./media/output"
    frames_dir: str = "./media/frames"
    thumbnails_dir: str = "./media/thumbnails"


class Settings(BaseSettings):
    """Root settings aggregating all configuration sections."""

    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    persistence_backend: str = "memory"  # "postgres" or "memory"

    # Authentication
    firebase: FirebaseSettings = Field(default_factory=FirebaseSettings)

    # Infrastructure
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    mlflow: MLflowSettings = Field(default_factory=MLflowSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)

    # AI / Analysis
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    multi_model: MultiModelSettings = Field(default_factory=MultiModelSettings)
    ai_analysis: AIAnalysisSettings = Field(default_factory=AIAnalysisSettings)
    advanced_analysis: AdvancedAnalysisSettings = Field(default_factory=AdvancedAnalysisSettings)

    # Video pipeline
    video: VideoSettings = Field(default_factory=VideoSettings)
    frame_extraction: FrameExtractionSettings = Field(default_factory=FrameExtractionSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)
    crop: CropSettings = Field(default_factory=CropSettings)
    composition: CompositionSettings = Field(default_factory=CompositionSettings)

    # Effects & overlays
    effects: EffectsSettings = Field(default_factory=EffectsSettings)
    text_overlay: TextOverlaySettings = Field(default_factory=TextOverlaySettings)
    audio_processing: AudioProcessingSettings = Field(default_factory=AudioProcessingSettings)

    # Pro features
    super_resolution: SuperResolutionSettings = Field(default_factory=SuperResolutionSettings)
    video_enhancer: VideoEnhancerSettings = Field(default_factory=VideoEnhancerSettings)
    audio_enhancer: AudioEnhancerSettings = Field(default_factory=AudioEnhancerSettings)
    subtitle_generator: SubtitleGeneratorSettings = Field(default_factory=SubtitleGeneratorSettings)
    smart_cropper: SmartCropperSettings = Field(default_factory=SmartCropperSettings)
    gpu_encoder: GPUEncoderSettings = Field(default_factory=GPUEncoderSettings)

    # Thumbnails & engagement
    thumbnail: ThumbnailSettings = Field(default_factory=ThumbnailSettings)
    thumbnail_ab_tester: ThumbnailABTesterSettings = Field(default_factory=ThumbnailABTesterSettings)
    engagement_predictor: EngagementPredictorSettings = Field(default_factory=EngagementPredictorSettings)
    chapter_generator: ChapterGeneratorSettings = Field(default_factory=ChapterGeneratorSettings)

    # Web server
    web: WebSettings = Field(default_factory=WebSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def validate_production(self) -> None:
        """Validate critical settings for production environment."""
        if self.app_env == "production" and self.secret_key == "change-me-in-production":
            raise RuntimeError(
                "FATAL: secret_key must be changed from default in production. "
                "Set the SECRET_KEY environment variable."
            )

    def to_legacy_dict(self) -> dict:
        """Convert to the legacy config dict format for backward compatibility."""
        return {
            "ollama": {
                "base_url": self.ollama.base_url,
                "vision_model": self.ollama.vision_model,
                "thinking_model": self.ollama.thinking_model,
                "timeout": self.ollama.timeout,
                "use_llamacpp": self.ollama.use_llamacpp,
            },
            "multi_model": {
                "enable": self.multi_model.enable,
                "strategy": self.multi_model.strategy,
                "models": self.multi_model.models,
                "confidence_threshold": self.multi_model.confidence_threshold,
                "parallel_processing": self.multi_model.parallel_processing,
            },
            "video": {
                "input_dir": self.video.input_dir,
                "output_dir": self.video.output_dir,
                "frames_dir": self.video.frames_dir,
                "sample_interval": self.video.sample_interval,
            },
            "frame_extraction": {
                "interval_seconds": self.frame_extraction.interval_seconds,
                "quality": self.frame_extraction.quality,
                "max_frames": self.frame_extraction.max_frames,
            },
            "export": {
                "codec": self.export.codec,
                "crf": self.export.crf,
                "preset": self.export.preset,
                "audio_bitrate": self.export.audio_bitrate,
                "maintain_fps": self.export.maintain_fps,
                "maintain_resolution": self.export.maintain_resolution,
            },
            "web": {
                "host": self.web.host,
                "port": self.web.port,
                "max_upload_size_mb": self.web.max_upload_size_mb,
                "allowed_extensions": self.web.allowed_extensions,
            },
            "logging": {"level": self.logging.level, "file": self.logging.file},
            "effects": {
                "enable": self.effects.enable,
                "color_grading": {
                    "enable": self.effects.color_grading.enable,
                    "preset": self.effects.color_grading.preset,
                },
                "vignette": {
                    "enable": self.effects.vignette.enable,
                    "intensity": self.effects.vignette.intensity,
                },
                "transition": {
                    "enable": self.effects.transition.enable,
                    "type": self.effects.transition.type,
                    "duration": self.effects.transition.duration,
                },
                "slow_motion": {
                    "enable": self.effects.slow_motion.enable,
                    "speed": self.effects.slow_motion.speed,
                    "apply_to_kills": self.effects.slow_motion.apply_to_kills,
                },
            },
            "text_overlay": {
                "enable": self.text_overlay.enable,
                "kill_counter": {
                    "enable": self.text_overlay.kill_counter.enable,
                    "font_size": self.text_overlay.kill_counter.font_size,
                    "color": self.text_overlay.kill_counter.color,
                    "position": self.text_overlay.kill_counter.position,
                },
                "kill_popups": {
                    "enable": self.text_overlay.kill_popups.enable,
                    "show_double_kill": self.text_overlay.kill_popups.show_double_kill,
                    "show_triple_kill": self.text_overlay.kill_popups.show_triple_kill,
                    "show_quad_kill": self.text_overlay.kill_popups.show_quad_kill,
                    "show_ace": self.text_overlay.kill_popups.show_ace,
                },
            },
            "audio_processing": {
                "enable": self.audio_processing.enable,
                "normalization": {"enable": self.audio_processing.normalization.enable},
                "enhancement": {"enable": self.audio_processing.enhancement.enable},
                "fade": {
                    "enable": self.audio_processing.fade.enable,
                    "fade_in": self.audio_processing.fade.fade_in,
                    "fade_out": self.audio_processing.fade.fade_out,
                },
                "background_music": {
                    "enable": self.audio_processing.background_music.enable,
                    "music_path": self.audio_processing.background_music.music_path,
                    "video_volume": self.audio_processing.background_music.video_volume,
                    "music_volume": self.audio_processing.background_music.music_volume,
                },
            },
            "composition": {
                "enable": self.composition.enable,
                "target_duration": self.composition.target_duration,
                "min_clip_length": self.composition.min_clip_length,
                "max_clip_length": self.composition.max_clip_length,
                "optimal_pace": self.composition.optimal_pace,
            },
            "thumbnail": {
                "enable": self.thumbnail.enable,
                "youtube": {"enable": self.thumbnail.youtube.enable},
                "short_video": {
                    "enable": self.thumbnail.short_video.enable,
                    "platforms": self.thumbnail.short_video.platforms,
                },
            },
            "advanced_analysis": {
                "enable": self.advanced_analysis.enable,
                "detect_multi_kills": self.advanced_analysis.detect_multi_kills,
                "multi_kill_window": self.advanced_analysis.multi_kill_window,
                "suggest_highlights": self.advanced_analysis.suggest_highlights,
            },
            "super_resolution": {
                "enable": self.super_resolution.enable,
                "scale": self.super_resolution.scale,
            },
            "video_enhancer": {
                "enable": self.video_enhancer.enable,
                "denoise": {"enable": self.video_enhancer.denoise.enable, "strength": self.video_enhancer.denoise.strength},
                "sharpen": {"enable": self.video_enhancer.sharpen.enable, "amount": self.video_enhancer.sharpen.amount},
                "lut": {"enable": self.video_enhancer.lut.enable, "preset": self.video_enhancer.lut.preset},
                "grain": {"enable": self.video_enhancer.grain.enable, "strength": self.video_enhancer.grain.strength},
            },
            "audio_enhancer": {"enable": self.audio_enhancer.enable},
            "subtitle_generator": {"enable": self.subtitle_generator.enable},
            "gpu_encoder": {
                "enable": self.gpu_encoder.enable,
                "codec": self.gpu_encoder.codec,
                "quality": self.gpu_encoder.quality,
            },
            "thumbnail_ab_tester": {"enable": self.thumbnail_ab_tester.enable},
            "engagement_predictor": {"enable": self.engagement_predictor.enable},
            "chapter_generator": {"enable": self.chapter_generator.enable},
            "smart_cropper": {"enable": self.smart_cropper.enable},
        }


def get_settings() -> Settings:
    """Create and return application settings."""
    return Settings()
