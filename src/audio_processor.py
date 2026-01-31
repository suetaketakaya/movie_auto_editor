"""
Audio Processing Module
オーディオの処理と改善
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional
import os
import shutil

logger = logging.getLogger(__name__)

# FFmpegパスを取得
def get_ffmpeg_path():
    """FFmpegの実行可能ファイルパスを取得"""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    possible_paths = [
        r"C:\Users\suetake\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_path()


class AudioProcessor:
    """オーディオ処理クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.audio_config = config.get("audio_processing", {})

    def add_background_music(self, video_path: str, music_path: str,
                            output_path: str, video_volume: float = 0.7,
                            music_volume: float = 0.3) -> str:
        """
        BGMを追加

        Args:
            video_path: 入力動画
            music_path: BGMファイル
            output_path: 出力パス
            video_volume: ゲーム音量（0.0-1.0）
            music_volume: BGM音量（0.0-1.0）
        """
        logger.info(f"Adding background music: {music_path}")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", video_path,
            "-stream_loop", "-1",  # BGMをループ
            "-i", music_path,
            "-filter_complex",
            f"[0:a]volume={video_volume}[a0];[1:a]volume={music_volume}[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",  # 動画の長さに合わせる
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Background music failed: {result.stderr}")
            raise RuntimeError("Background music addition failed")

        return str(output_path)

    def add_sound_effect(self, video_path: str, sound_path: str,
                        output_path: str, timestamp: float,
                        volume: float = 1.0) -> str:
        """
        効果音を追加

        Args:
            video_path: 入力動画
            sound_path: 効果音ファイル
            output_path: 出力パス
            timestamp: 効果音を再生する時間（秒）
            volume: 音量（0.0-2.0）
        """
        logger.info(f"Adding sound effect at {timestamp}s")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", video_path,
            "-i", sound_path,
            "-filter_complex",
            f"[1:a]adelay={int(timestamp*1000)}|{int(timestamp*1000)},volume={volume}[sfx];"
            f"[0:a][sfx]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Sound effect failed: {result.stderr}")
            raise RuntimeError("Sound effect addition failed")

        return str(output_path)

    def normalize_audio(self, input_path: str, output_path: str,
                       target_level: str = "-23dB") -> str:
        """
        音量を正規化（ラウドネスノーマライゼーション）

        Args:
            input_path: 入力動画
            output_path: 出力パス
            target_level: 目標ラウドネス（-23dB for YouTube, -14dB for Spotify）
        """
        logger.info(f"Normalizing audio to {target_level}")

        # EBU R128ラウドネス正規化
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-af", f"loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Audio normalization failed: {result.stderr}")
            raise RuntimeError("Audio normalization failed")

        return str(output_path)

    def enhance_game_audio(self, input_path: str, output_path: str) -> str:
        """
        ゲーム音声を強調（銃声・足音を強調）

        Args:
            input_path: 入力動画
            output_path: 出力パス
        """
        logger.info("Enhancing game audio")

        # 中域・高域を強調して銃声を際立たせる
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-af", "equalizer=f=2000:width_type=h:width=1000:g=3,equalizer=f=8000:width_type=h:width=2000:g=2",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Audio enhancement failed: {result.stderr}")
            raise RuntimeError("Audio enhancement failed")

        return str(output_path)

    def remove_background_noise(self, input_path: str, output_path: str) -> str:
        """
        背景ノイズを除去

        Args:
            input_path: 入力動画
            output_path: 出力パス
        """
        logger.info("Removing background noise")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-af", "highpass=f=200,lowpass=f=3000,afftdn=nf=-25",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Noise removal failed: {result.stderr}")
            raise RuntimeError("Noise removal failed")

        return str(output_path)

    def add_bass_boost(self, input_path: str, output_path: str,
                      gain: int = 5) -> str:
        """
        低音ブースト（インパクトを強調）

        Args:
            input_path: 入力動画
            output_path: 出力パス
            gain: ゲイン（dB）
        """
        logger.info(f"Adding bass boost: +{gain}dB")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-af", f"equalizer=f=100:width_type=h:width=50:g={gain}",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Bass boost failed: {result.stderr}")
            raise RuntimeError("Bass boost failed")

        return str(output_path)

    def create_audio_ducking(self, video_path: str, music_path: str,
                           output_path: str, threshold: float = -20,
                           ratio: float = 4) -> str:
        """
        オーディオダッキング（ゲーム音が大きい時にBGMを下げる）

        Args:
            video_path: 入力動画
            music_path: BGMファイル
            output_path: 出力パス
            threshold: ダッキング開始レベル（dB）
            ratio: 圧縮比
        """
        logger.info("Creating audio ducking")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", video_path,
            "-stream_loop", "-1",
            "-i", music_path,
            "-filter_complex",
            f"[0:a][1:a]sidechaincompress=threshold={threshold}:ratio={ratio}:attack=1000:release=2000[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Audio ducking failed: {result.stderr}")
            raise RuntimeError("Audio ducking failed")

        return str(output_path)

    def fade_in_out(self, input_path: str, output_path: str,
                    fade_in: float = 1.0, fade_out: float = 1.0) -> str:
        """
        フェードイン・フェードアウトを追加

        Args:
            input_path: 入力動画
            output_path: 出力パス
            fade_in: フェードイン時間（秒）
            fade_out: フェードアウト時間（秒）
        """
        logger.info(f"Adding fade in ({fade_in}s) and fade out ({fade_out}s)")

        # まず動画の長さを取得
        probe_cmd = [
            FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe"),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path
        ]

        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())

        fade_out_start = duration - fade_out

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-af", f"afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}",
            "-c:v", "copy",
            "-c:a", "aac",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Fade in/out failed: {result.stderr}")
            raise RuntimeError("Fade in/out failed")

        return str(output_path)
