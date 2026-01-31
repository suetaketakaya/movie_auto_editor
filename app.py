"""
Auto-FPS-Clipper - Web Application (Enhanced Version)
FPSゲームのハイライト動画自動生成システム - プロ品質編集機能搭載
"""

from fastapi import FastAPI, File, UploadFile, WebSocket, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
import yaml
import logging
import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Optional
import json
from datetime import datetime
import shutil

# Import custom modules - Original
from src.frame_extractor import FrameExtractor
from src.ollama_client import OllamaClient
from src.video_editor import VideoEditor

# Import custom modules - Enhanced Features (v2.0)
from src.effects import VisualEffects
from src.text_overlay import TextOverlay
from src.audio_processor import AudioProcessor
from src.composition_optimizer import CompositionOptimizer
from src.thumbnail_generator import ThumbnailGenerator
from src.advanced_analyzer import AdvancedAnalyzer

# Import custom modules - Pro Features (v3.0) - Optional imports
try:
    from src.super_resolution import SuperResolution
    SUPER_RESOLUTION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SuperResolution not available: {e}")
    SUPER_RESOLUTION_AVAILABLE = False

try:
    from src.video_enhancer import VideoEnhancer
    VIDEO_ENHANCER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"VideoEnhancer not available: {e}")
    VIDEO_ENHANCER_AVAILABLE = False

try:
    from src.audio_enhancer import AudioEnhancer
    AUDIO_ENHANCER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"AudioEnhancer not available: {e}")
    AUDIO_ENHANCER_AVAILABLE = False

try:
    from src.subtitle_generator import SubtitleGenerator
    SUBTITLE_GENERATOR_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SubtitleGenerator not available: {e}")
    SUBTITLE_GENERATOR_AVAILABLE = False

try:
    from src.smart_cropper import SmartCropper
    SMART_CROPPER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SmartCropper not available: {e}")
    SMART_CROPPER_AVAILABLE = False

try:
    from src.gpu_encoder import GPUEncoder
    GPU_ENCODER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"GPUEncoder not available: {e}")
    GPU_ENCODER_AVAILABLE = False

try:
    from src.thumbnail_ab_tester import ThumbnailABTester
    THUMBNAIL_AB_TESTER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"ThumbnailABTester not available: {e}")
    THUMBNAIL_AB_TESTER_AVAILABLE = False

try:
    from src.engagement_predictor import EngagementPredictor
    ENGAGEMENT_PREDICTOR_AVAILABLE = True
except ImportError as e:
    logging.warning(f"EngagementPredictor not available: {e}")
    ENGAGEMENT_PREDICTOR_AVAILABLE = False

try:
    from src.chapter_generator import ChapterGenerator
    CHAPTER_GENERATOR_AVAILABLE = True
except ImportError as e:
    logging.warning(f"ChapterGenerator not available: {e}")
    CHAPTER_GENERATOR_AVAILABLE = False

from src.multi_model_analyzer import MultiModelAnalyzer

# Load configuration
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Setup logging
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"]),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(config["logging"]["file"], encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Auto-FPS-Clipper Pro",
    description="AI-powered FPS game highlight video generator with professional editing features",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Create necessary directories
for directory in ["uploads", "frames", "output", "logs", "thumbnails"]:
    Path(directory).mkdir(exist_ok=True)

# Active processing jobs
active_jobs: Dict[str, Dict] = {}

# WebSocket connections
active_connections: List[WebSocket] = []


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        self.active_connections[job_id] = websocket
        logger.info(f"WebSocket connected for job: {job_id}")

    def disconnect(self, job_id: str):
        if job_id in self.active_connections:
            del self.active_connections[job_id]
            logger.info(f"WebSocket disconnected for job: {job_id}")

    async def send_progress(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            try:
                await self.active_connections[job_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending progress: {e}")
                self.disconnect(job_id)


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render main page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload video file"""
    try:
        # Validate file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in config["web"]["allowed_extensions"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {config['web']['allowed_extensions']}"
            )

        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Save uploaded file
        upload_path = Path("uploads") / f"{job_id}_{file.filename}"

        logger.info(f"Uploading file: {file.filename} (Job ID: {job_id})")

        with open(upload_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Create job entry
        active_jobs[job_id] = {
            "id": job_id,
            "filename": file.filename,
            "upload_path": str(upload_path),
            "status": "uploaded",
            "created_at": datetime.now().isoformat(),
            "progress": 0
        }

        logger.info(f"File uploaded successfully: {upload_path}")

        return {
            "job_id": job_id,
            "filename": file.filename,
            "message": "File uploaded successfully"
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process/{job_id}")
async def process_video(job_id: str):
    """Start video processing"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    if job["status"] != "uploaded":
        raise HTTPException(status_code=400, detail="Job already processing or completed")

    # Update job status
    job["status"] = "processing"
    job["progress"] = 0

    # Start processing in background
    asyncio.create_task(process_video_task(job_id))

    return {"message": "Processing started", "job_id": job_id}


async def process_video_task(job_id: str):
    """
    Enhanced background task for video processing
    全機能統合版
    """
    try:
        job = active_jobs[job_id]
        video_path = job["upload_path"]

        # Initialize all components
        frame_extractor = FrameExtractor(config)

        # マルチモデル分析 or シングルモデル
        if config.get("multi_model", {}).get("enable", False):
            ai_analyzer = MultiModelAnalyzer(config)
            logger.info("Using multi-model analysis for higher accuracy")
        else:
            ai_analyzer = OllamaClient(config)
            logger.info("Using single-model analysis")

        video_editor = VideoEditor(config)

        # Enhanced modules (v2.0)
        visual_effects = VisualEffects(config)
        text_overlay = TextOverlay(config)
        audio_processor = AudioProcessor(config)
        composition_optimizer = CompositionOptimizer(config)
        thumbnail_generator = ThumbnailGenerator(config)
        advanced_analyzer = AdvancedAnalyzer(config)

        # Pro modules (v3.0) - Initialize only if available
        super_resolution = SuperResolution(config) if SUPER_RESOLUTION_AVAILABLE else None
        video_enhancer = VideoEnhancer(config) if VIDEO_ENHANCER_AVAILABLE else None
        audio_enhancer = AudioEnhancer(config) if AUDIO_ENHANCER_AVAILABLE else None
        subtitle_generator = SubtitleGenerator(config) if SUBTITLE_GENERATOR_AVAILABLE else None
        smart_cropper = SmartCropper(config) if SMART_CROPPER_AVAILABLE else None
        gpu_encoder = GPUEncoder(config) if GPU_ENCODER_AVAILABLE else None
        thumbnail_ab_tester = ThumbnailABTester(config) if THUMBNAIL_AB_TESTER_AVAILABLE else None
        engagement_predictor = EngagementPredictor(config) if ENGAGEMENT_PREDICTOR_AVAILABLE else None
        chapter_generator = ChapterGenerator(config) if CHAPTER_GENERATOR_AVAILABLE else None

        # ========== STEP 1: Extract frames ==========
        await manager.send_progress(job_id, {
            "stage": "frame_extraction",
            "progress": 5,
            "message": "🎬 フレームを抽出しています..."
        })

        frames_dir = Path("frames") / job_id
        frames_dir.mkdir(exist_ok=True)

        frames = await frame_extractor.extract_frames(video_path, frames_dir)
        job["frames_count"] = len(frames)
        logger.info(f"Extracted {len(frames)} frames")

        # ========== STEP 2: AI Analysis with Ollama Vision ==========
        await manager.send_progress(job_id, {
            "stage": "ai_analysis",
            "progress": 10,
            "message": "🤖 AI解析を実行しています..."
        })

        analysis_results = []
        for i, frame_path in enumerate(frames):
            result = await ai_analyzer.analyze_frame(frame_path)
            analysis_results.append(result)

            progress = 10 + int((i / len(frames)) * 30)
            if i % 10 == 0:  # 10フレームごとに進捗更新
                await manager.send_progress(job_id, {
                    "stage": "ai_analysis",
                    "progress": progress,
                    "message": f"🔍 フレーム解析中: {i+1}/{len(frames)}"
                })

        job["analysis_results"] = analysis_results
        logger.info(f"Analyzed {len(analysis_results)} frames")

        # ========== STEP 3: Advanced AI Analysis ==========
        if config.get("advanced_analysis", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "advanced_analysis",
                "progress": 40,
                "message": "🧠 高度なAI分析を実行しています..."
            })

            # 興奮度分析
            analysis_results = advanced_analyzer.analyze_excitement_level(analysis_results)

            # マルチキル検出
            multi_kills = advanced_analyzer.detect_multi_kills(analysis_results)
            job["multi_kills"] = multi_kills
            logger.info(f"Detected {len(multi_kills)} multi-kill events")

            # クラッチモーメント検出
            clutch_moments = advanced_analyzer.detect_clutch_moments(analysis_results)
            job["clutch_moments"] = clutch_moments

            # パターンベースのハイライト提案
            suggested_highlights = advanced_analyzer.suggest_highlights_from_patterns(
                analysis_results, multi_kills, clutch_moments
            )

        # ========== STEP 4: Determine Clips ==========
        await manager.send_progress(job_id, {
            "stage": "clip_detection",
            "progress": 50,
            "message": "✂️ ハイライトシーンを検出しています..."
        })

        if config.get("advanced_analysis", {}).get("suggest_highlights", True) and suggested_highlights:
            # 高度な分析による推奨ハイライトを使用
            clips = suggested_highlights
            logger.info(f"Using AI-suggested highlights: {len(clips)} clips")
        else:
            # 従来のThinking modelによる判定
            # MultiModelAnalyzerの場合は、プライマリモデルのクライアントを使用
            if isinstance(ai_analyzer, MultiModelAnalyzer):
                thinking_client = list(ai_analyzer.clients.values())[0]
            else:
                thinking_client = ai_analyzer
            clips = await thinking_client.determine_clips(analysis_results)

        job["clips_raw"] = clips

        # ========== STEP 5: Composition Optimization ==========
        if config.get("composition", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "composition_optimization",
                "progress": 55,
                "message": "🎯 動画構成を最適化しています..."
            })

            clips = composition_optimizer.optimize_clips(clips, analysis_results)
            job["clips_optimized"] = clips
            logger.info(f"Optimized to {len(clips)} clips")

            # エンゲージメント分析
            engagement_analysis = composition_optimizer.analyze_engagement_curve(clips)
            job["engagement_analysis"] = engagement_analysis

        # ========== STEP 6: Generate Base Highlight Video ==========
        await manager.send_progress(job_id, {
            "stage": "video_generation",
            "progress": 60,
            "message": "🎥 ベース動画を生成しています..."
        })

        output_base = Path("output") / f"{job_id}_base.mp4"
        await video_editor.create_highlight(video_path, clips, output_base)
        logger.info(f"Base video created: {output_base}")

        current_video = str(output_base)

        # ========== STEP 7: Apply Visual Effects ==========
        if config.get("effects", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "effects",
                "progress": 65,
                "message": "✨ 視覚エフェクトを適用しています..."
            })

            effects_config = config.get("effects", {})

            # カラーグレーディング
            if effects_config.get("color_grading", {}).get("enable", True):
                temp_output = Path("output") / f"{job_id}_graded.mp4"
                preset = effects_config.get("color_grading", {}).get("preset", "cinematic")
                current_video = visual_effects.apply_color_grading(current_video, temp_output, preset)
                logger.info(f"Applied color grading: {preset}")

            # ビネット効果
            if effects_config.get("vignette", {}).get("enable", True):
                temp_output = Path("output") / f"{job_id}_vignette.mp4"
                intensity = effects_config.get("vignette", {}).get("intensity", 0.3)
                current_video = visual_effects.apply_vignette(current_video, temp_output, intensity)
                logger.info("Applied vignette effect")

        # ========== STEP 8: Apply Text Overlays ==========
        if config.get("text_overlay", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "text_overlay",
                "progress": 70,
                "message": "📝 テキストオーバーレイを追加しています..."
            })

            text_config = config.get("text_overlay", {})

            # キル数カウンター
            if text_config.get("kill_counter", {}).get("enable", True):
                temp_output = Path("output") / f"{job_id}_kill_counter.mp4"
                kill_timestamps = [r["timestamp"] for r in analysis_results if r.get("kill_log", False)]
                if kill_timestamps:
                    current_video = text_overlay.add_kill_counter(current_video, temp_output, kill_timestamps)
                    logger.info(f"Added kill counter: {len(kill_timestamps)} kills")

            # マルチキルポップアップ
            if text_config.get("kill_popups", {}).get("enable", True) and multi_kills:
                for mk in multi_kills:
                    temp_output = Path("output") / f"{job_id}_popup_{mk['type']}.mp4"
                    current_video = text_overlay.add_text_popup(
                        current_video, temp_output,
                        mk['type'], mk['timestamp'], 2.0, "center"
                    )
                    logger.info(f"Added {mk['type']} popup at {mk['timestamp']}s")

        # ========== STEP 9: Audio Processing ==========
        if config.get("audio_processing", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "audio_processing",
                "progress": 75,
                "message": "🎵 オーディオを処理しています..."
            })

            audio_config = config.get("audio_processing", {})

            # 音量正規化
            if audio_config.get("normalization", {}).get("enable", True):
                temp_output = Path("output") / f"{job_id}_normalized.mp4"
                current_video = audio_processor.normalize_audio(current_video, temp_output)
                logger.info("Applied audio normalization")

            # ゲーム音声強調
            if audio_config.get("enhancement", {}).get("enable", True):
                temp_output = Path("output") / f"{job_id}_enhanced.mp4"
                current_video = audio_processor.enhance_game_audio(current_video, temp_output)
                logger.info("Enhanced game audio")

            # フェードイン/アウト
            if audio_config.get("fade", {}).get("enable", True):
                temp_output = Path("output") / f"{job_id}_faded.mp4"
                fade_in = audio_config.get("fade", {}).get("fade_in", 1.0)
                fade_out = audio_config.get("fade", {}).get("fade_out", 1.0)
                current_video = audio_processor.fade_in_out(current_video, temp_output, fade_in, fade_out)
                logger.info("Applied fade in/out")

            # BGM追加
            if audio_config.get("background_music", {}).get("enable", False):
                music_path = audio_config.get("background_music", {}).get("music_path", "")
                if music_path and Path(music_path).exists():
                    temp_output = Path("output") / f"{job_id}_with_music.mp4"
                    video_vol = audio_config.get("background_music", {}).get("video_volume", 0.7)
                    music_vol = audio_config.get("background_music", {}).get("music_volume", 0.3)
                    current_video = audio_processor.add_background_music(
                        current_video, music_path, temp_output, video_vol, music_vol
                    )
                    logger.info("Added background music")

        # ========== STEP 10: Finalize Main Video ==========
        final_output = Path("output") / f"{job_id}_highlight.mp4"
        if current_video != str(final_output):
            shutil.move(current_video, final_output)

        job["output_path"] = str(final_output)
        logger.info(f"Main video completed: {final_output}")

        # ========== PRO FEATURES (v3.0) ==========

        # ========== STEP 10.1: Video Enhancement ==========
        if config.get("video_enhancer", {}).get("enable", True) and video_enhancer:
            await manager.send_progress(job_id, {
                "stage": "video_enhancement",
                "progress": 72,
                "message": "✨ 動画品質を向上させています..."
            })

            enhanced_output = Path("output") / f"{job_id}_enhanced.mp4"
            final_output = Path(video_enhancer.apply_all_enhancements(str(final_output), str(enhanced_output)))
            logger.info("Video enhancement completed")

        # ========== STEP 10.2: Audio Enhancement ==========
        if config.get("audio_enhancer", {}).get("enable", True) and audio_enhancer:
            await manager.send_progress(job_id, {
                "stage": "audio_enhancement",
                "progress": 74,
                "message": "🎵 音声品質を向上させています..."
            })

            audio_enhanced = Path("output") / f"{job_id}_audio_enhanced.mp4"
            final_output = Path(audio_enhancer.enhance_voice_clarity(str(final_output), str(audio_enhanced)))
            logger.info("Audio enhancement completed")

        # ========== STEP 10.3: Super Resolution Upscaling ==========
        if config.get("super_resolution", {}).get("enable", False) and super_resolution:  # デフォルトOFF (処理時間長い)
            await manager.send_progress(job_id, {
                "stage": "super_resolution",
                "progress": 76,
                "message": "🔬 AI超解像処理を実行しています..."
            })

            sr_config = config.get("super_resolution", {})
            scale = sr_config.get("scale", 2)
            upscaled_output = Path("output") / f"{job_id}_upscaled.mp4"
            final_output = Path(super_resolution.upscale_video(str(final_output), str(upscaled_output), scale))
            logger.info(f"Super resolution upscaling completed: {scale}x")

        # ========== STEP 10.4: GPU Encoding ==========
        if config.get("gpu_encoder", {}).get("enable", True) and gpu_encoder:
            await manager.send_progress(job_id, {
                "stage": "gpu_encoding",
                "progress": 78,
                "message": "⚡ GPU高速エンコード中..."
            })

            gpu_config = config.get("gpu_encoder", {})
            codec = gpu_config.get("codec", "h264")
            quality = gpu_config.get("quality", "high")
            gpu_output = Path("output") / f"{job_id}_gpu_encoded.mp4"
            final_output = Path(gpu_encoder.encode_video(str(final_output), str(gpu_output), codec, quality))
            logger.info(f"GPU encoding completed: {codec} @ {quality}")

        # ========== STEP 10.5: Subtitle Generation ==========
        if config.get("subtitle_generator", {}).get("enable", False) and subtitle_generator:  # デフォルトOFF
            await manager.send_progress(job_id, {
                "stage": "subtitle_generation",
                "progress": 80,
                "message": "💬 自動字幕を生成しています..."
            })

            srt_output = Path("output") / f"{job_id}_subtitles.srt"
            subtitle_generator.generate_subtitles(video_path, str(srt_output))

            if config.get("subtitle_generator", {}).get("burn_into_video", True):
                subtitled_output = Path("output") / f"{job_id}_subtitled.mp4"
                final_output = Path(subtitle_generator.burn_subtitles(str(final_output), str(srt_output), str(subtitled_output)))
                logger.info("Subtitles generated and burned into video")

        # ========== STEP 10.6: Engagement Prediction ==========
        if config.get("engagement_predictor", {}).get("enable", True) and engagement_predictor:
            await manager.send_progress(job_id, {
                "stage": "engagement_prediction",
                "progress": 82,
                "message": "📊 エンゲージメントを予測しています..."
            })

            engagement_scores = engagement_predictor.predict_engagement_score(clips, analysis_results)
            job["engagement_prediction"] = engagement_scores
            logger.info(f"Engagement prediction: {engagement_scores['overall_score']}/100")

        # ========== STEP 10.7: Chapter Generation ==========
        if config.get("chapter_generator", {}).get("enable", True) and chapter_generator:
            await manager.send_progress(job_id, {
                "stage": "chapter_generation",
                "progress": 83,
                "message": "📖 チャプターを生成しています..."
            })

            chapters = chapter_generator.generate_chapters(clips, multi_kills)
            chapter_file = Path("output") / f"{job_id}_chapters.txt"
            chapter_generator.export_youtube_description(chapters, str(chapter_file))
            job["chapters"] = chapters
            logger.info(f"Generated {len(chapters)} chapters")

        # ========== STEP 11: Generate Thumbnail & A/B Variants ==========
        if config.get("thumbnail", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "thumbnail_generation",
                "progress": 85,
                "message": "🖼️ サムネイルを生成しています..."
            })

            thumb_config = config.get("thumbnail", {})

            # 最高スコアのクリップからサムネイル生成
            if clips:
                best_clip = max(clips, key=lambda x: x.get("score", 0))
                best_timestamp = (best_clip["start"] + best_clip["end"]) / 2

                # フレーム抽出
                thumb_frame = Path("thumbnails") / f"{job_id}_frame.jpg"
                thumbnail_generator.extract_best_frame(video_path, best_timestamp, thumb_frame)

                # YouTubeサムネイル
                if thumb_config.get("youtube", {}).get("enable", True):
                    thumb_output = Path("thumbnails") / f"{job_id}_youtube.jpg"
                    kill_count = len([r for r in analysis_results if r.get("kill_log", False)])
                    thumbnail_generator.create_youtube_thumbnail(
                        thumb_frame, thumb_output,
                        title_text="EPIC HIGHLIGHTS",
                        kill_count=kill_count
                    )
                    job["thumbnail_path"] = str(thumb_output)
                    logger.info(f"YouTube thumbnail created: {thumb_output}")

                # A/Bテストサムネイル生成
                if config.get("thumbnail_ab_tester", {}).get("enable", True):
                    variants_dir = Path("thumbnails") / f"{job_id}_variants"
                    variants_dir.mkdir(exist_ok=True)
                    kill_count = len([r for r in analysis_results if r.get("kill_log", False)])
                    thumbnail_variants = thumbnail_ab_tester.generate_multiple_variants(
                        video_path, str(variants_dir),
                        title="EPIC HIGHLIGHTS",
                        kill_count=kill_count
                    )
                    job["thumbnail_variants"] = thumbnail_variants
                    logger.info(f"Generated {len(thumbnail_variants)} thumbnail A/B variants")

        # ========== STEP 12: Generate Short Videos ==========
        if config.get("thumbnail", {}).get("short_video", {}).get("enable", True):
            await manager.send_progress(job_id, {
                "stage": "short_video_generation",
                "progress": 90,
                "message": "📱 ショート動画を生成しています..."
            })

            short_config = config.get("thumbnail", {}).get("short_video", {})
            platforms = short_config.get("platforms", [])

            # YouTube Shorts
            if "youtube_shorts" in platforms:
                shorts_output = Path("output") / f"{job_id}_shorts.mp4"
                thumbnail_generator.create_short_video(str(final_output), shorts_output, "center")
                job["shorts_path"] = str(shorts_output)
                logger.info(f"YouTube Shorts created: {shorts_output}")

            # Instagram Reel
            if "instagram_reel" in platforms:
                reel_output = Path("output") / f"{job_id}_reel.mp4"
                thumbnail_generator.create_instagram_reel(str(final_output), reel_output)
                job["reel_path"] = str(reel_output)
                logger.info(f"Instagram Reel created: {reel_output}")

            # TikTok
            if "tiktok" in platforms:
                tiktok_output = Path("output") / f"{job_id}_tiktok.mp4"
                thumbnail_generator.create_tiktok_video(str(final_output), tiktok_output)
                job["tiktok_path"] = str(tiktok_output)
                logger.info(f"TikTok video created: {tiktok_output}")

        # ========== STEP 13: Cleanup Temporary Files ==========
        await manager.send_progress(job_id, {
            "stage": "cleanup",
            "progress": 95,
            "message": "🧹 一時ファイルを削除しています..."
        })

        # 中間ファイルを削除
        output_dir = Path("output")
        for temp_file in output_dir.glob(f"{job_id}_*.mp4"):
            if temp_file != final_output and "shorts" not in temp_file.name and "reel" not in temp_file.name and "tiktok" not in temp_file.name:
                try:
                    temp_file.unlink()
                except:
                    pass

        # ========== COMPLETION ==========
        job["status"] = "completed"
        job["progress"] = 100

        await manager.send_progress(job_id, {
            "stage": "completed",
            "progress": 100,
            "message": "✅ 処理が完了しました！",
            "output_file": f"/api/download/{job_id}",
            "outputs": {
                "main_video": f"/api/download/{job_id}",
                "thumbnail": f"/api/download/{job_id}/thumbnail" if "thumbnail_path" in job else None,
                "shorts": f"/api/download/{job_id}/shorts" if "shorts_path" in job else None,
                "reel": f"/api/download/{job_id}/reel" if "reel_path" in job else None,
                "tiktok": f"/api/download/{job_id}/tiktok" if "tiktok_path" in job else None,
            }
        })

        logger.info(f"✅ Processing completed for job: {job_id}")
        logger.info(f"Stats: {len(frames)} frames, {len(clips)} clips, {len(multi_kills)} multi-kills")

    except Exception as e:
        logger.error(f"❌ Processing error for job {job_id}: {e}", exc_info=True)
        job["status"] = "failed"
        job["error"] = str(e)

        await manager.send_progress(job_id, {
            "stage": "failed",
            "progress": 0,
            "message": f"❌ エラーが発生しました: {str(e)}"
        })


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress updates"""
    await manager.connect(websocket, job_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(job_id)


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return active_jobs[job_id]


@app.get("/api/download/{job_id}")
@app.get("/api/download/{job_id}/{output_type}")
async def download_video(job_id: str, output_type: str = "main"):
    """Download processed video or thumbnail"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    # 出力タイプに応じたファイルパスを取得
    path_map = {
        "main": job.get("output_path"),
        "thumbnail": job.get("thumbnail_path"),
        "shorts": job.get("shorts_path"),
        "reel": job.get("reel_path"),
        "tiktok": job.get("tiktok_path")
    }

    output_path = path_map.get(output_type)

    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail=f"{output_type} file not found")

    # ファイル拡張子を判定
    is_image = output_path.endswith(('.jpg', '.png', '.jpeg'))
    media_type = "image/jpeg" if is_image else "video/mp4"

    filename = f"{output_type}_{job['filename']}" if output_type != "main" else f"highlight_{job['filename']}"

    return FileResponse(
        output_path,
        media_type=media_type,
        filename=filename
    )


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs"""
    return {"jobs": list(active_jobs.values())}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    # Delete files
    try:
        if os.path.exists(job["upload_path"]):
            os.remove(job["upload_path"])

        # Delete all output files
        for key in ["output_path", "thumbnail_path", "shorts_path", "reel_path", "tiktok_path"]:
            if key in job and os.path.exists(job[key]):
                os.remove(job[key])

        # Delete frames directory
        frames_dir = Path("frames") / job_id
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
    except Exception as e:
        logger.error(f"Error deleting files for job {job_id}: {e}")

    # Remove from active jobs
    del active_jobs[job_id]

    return {"message": "Job deleted successfully"}


if __name__ == "__main__":
    import uvicorn

    host = config["web"]["host"]
    port = config["web"]["port"]

    logger.info(f"🚀 Starting Auto-FPS-Clipper Pro on {host}:{port}")
    logger.info(f"📦 Enhanced features enabled: Effects, Text Overlay, Audio Processing, AI Analysis")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,
        log_level=config["logging"]["level"].lower()
    )
