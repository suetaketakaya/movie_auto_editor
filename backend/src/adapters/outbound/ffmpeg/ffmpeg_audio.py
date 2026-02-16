"""FFmpeg adapter for audio processing operations.

Wraps legacy AudioProcessor and AudioEnhancer into a single adapter
implementing AudioProcessingPort.
"""
from __future__ import annotations

import asyncio
import logging

from backend.src.adapters.outbound.ffmpeg.ffmpeg_base import (
    get_video_duration,
    run_ffmpeg,
)

logger = logging.getLogger(__name__)

# Presets for enhance_audio (maps preset name -> af filter chain)
_ENHANCE_PRESETS: dict[str, str] = {
    "game": (
        "equalizer=f=2000:width_type=h:width=1000:g=3,"
        "equalizer=f=8000:width_type=h:width=2000:g=2"
    ),
    "voice": (
        "equalizer=f=300:width_type=o:width=2:g=3,"
        "equalizer=f=3000:width_type=o:width=2:g=5,"
        "acompressor=threshold=-20dB:ratio=4:attack=5:release=50,"
        "agate=threshold=-50dB:ratio=2"
    ),
    "noise_remove": "highpass=f=200,lowpass=f=3000,afftdn=nf=-25",
}


class FFmpegAudioProcessor:
    """Implements AudioProcessingPort using FFmpeg CLI."""

    def __init__(self, config: dict) -> None:
        self.config = config

    # -- port interface ---------------------------------------------------------

    def add_background_music(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        video_volume: float = 0.7,
        music_volume: float = 0.3,
    ) -> str:
        logger.info("Adding background music: %s", music_path)
        run_ffmpeg([
            "-i", video_path,
            "-stream_loop", "-1",
            "-i", music_path,
            "-filter_complex",
            (
                f"[0:a]volume={video_volume}[a0];"
                f"[1:a]volume={music_volume}[a1];"
                f"[a0][a1]amix=inputs=2:duration=first[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ])
        return str(output_path)

    def normalize_audio(self, input_path: str, output_path: str) -> str:
        logger.info("Normalizing audio (EBU R128)")
        run_ffmpeg([
            "-i", input_path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "320k",
            str(output_path),
        ])
        return str(output_path)

    def enhance_game_audio(self, input_path: str, output_path: str) -> str:
        return self.enhance_audio(input_path, output_path, preset="game")

    def add_sound_effect(
        self,
        video_path: str,
        sound_path: str,
        output_path: str,
        timestamp: float,
        volume: float = 1.0,
    ) -> str:
        logger.info("Adding sound effect at %.2fs", timestamp)
        delay_ms = int(timestamp * 1000)
        run_ffmpeg([
            "-i", video_path,
            "-i", sound_path,
            "-filter_complex",
            (
                f"[1:a]adelay={delay_ms}|{delay_ms},volume={volume}[sfx];"
                f"[0:a][sfx]amix=inputs=2:duration=first[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            str(output_path),
        ])
        return str(output_path)

    def enhance_audio(
        self, input_path: str, output_path: str, preset: str = "game"
    ) -> str:
        logger.info("Enhancing audio with preset: %s", preset)
        af = _ENHANCE_PRESETS.get(preset, _ENHANCE_PRESETS["game"])
        run_ffmpeg([
            "-i", input_path,
            "-af", af,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "320k",
            str(output_path),
        ])
        return str(output_path)

    def add_bass_boost(
        self, input_path: str, output_path: str, gain: int = 5
    ) -> str:
        logger.info("Adding bass boost: +%ddB", gain)
        run_ffmpeg([
            "-i", input_path,
            "-af", f"equalizer=f=100:width_type=h:width=50:g={gain}",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "320k",
            str(output_path),
        ])
        return str(output_path)

    def fade_in_out(
        self,
        input_path: str,
        output_path: str,
        fade_in: float = 1.0,
        fade_out: float = 1.0,
    ) -> str:
        logger.info("Adding audio fade in (%.1fs) / fade out (%.1fs)", fade_in, fade_out)
        duration = get_video_duration(input_path)
        fade_out_start = duration - fade_out

        run_ffmpeg([
            "-i", input_path,
            "-af",
            f"afade=t=in:st=0:d={fade_in},afade=t=out:st={fade_out_start}:d={fade_out}",
            "-c:v", "copy",
            "-c:a", "aac",
            str(output_path),
        ])
        return str(output_path)

    def remove_background_noise(self, input_path: str, output_path: str) -> str:
        return self.enhance_audio(input_path, output_path, preset="noise_remove")

    def create_audio_ducking(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        threshold: float = -20,
        ratio: float = 4,
    ) -> str:
        logger.info("Creating audio ducking")
        run_ffmpeg([
            "-i", video_path,
            "-stream_loop", "-1",
            "-i", music_path,
            "-filter_complex",
            (
                f"[0:a][1:a]sidechaincompress="
                f"threshold={threshold}:ratio={ratio}:"
                f"attack=1000:release=2000[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ])
        return str(output_path)

    # -- async convenience wrappers ---------------------------------------------

    async def add_background_music_async(
        self, video_path: str, music_path: str, output_path: str,
        video_volume: float = 0.7, music_volume: float = 0.3,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.add_background_music, video_path, music_path,
            output_path, video_volume, music_volume,
        )

    async def normalize_audio_async(
        self, input_path: str, output_path: str,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.normalize_audio, input_path, output_path,
        )

    async def add_sound_effect_async(
        self, video_path: str, sound_path: str, output_path: str,
        timestamp: float, volume: float = 1.0,
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.add_sound_effect, video_path, sound_path,
            output_path, timestamp, volume,
        )

    async def enhance_audio_async(
        self, input_path: str, output_path: str, preset: str = "game",
    ) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.enhance_audio, input_path, output_path, preset,
        )
