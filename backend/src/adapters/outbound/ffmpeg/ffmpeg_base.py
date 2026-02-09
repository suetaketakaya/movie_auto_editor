"""
Shared FFmpeg path resolution and command execution utilities.
Consolidates duplicate get_ffmpeg_path() from 5 legacy modules.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Common Windows FFmpeg install locations
_WINDOWS_FFMPEG_PATHS = [
    r"C:\Users\suetake\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]


def get_ffmpeg_path() -> str:
    """Resolve ffmpeg executable path. Checks PATH first, then known locations."""
    path = shutil.which("ffmpeg")
    if path:
        return path

    for candidate in _WINDOWS_FFMPEG_PATHS:
        if os.path.exists(candidate):
            logger.info("Found FFmpeg at: %s", candidate)
            return candidate

    return "ffmpeg"


def get_ffprobe_path() -> str:
    """Resolve ffprobe executable path derived from ffmpeg path."""
    ffmpeg = get_ffmpeg_path()
    if "ffmpeg.exe" in ffmpeg:
        probe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe")
        if os.path.exists(probe):
            return probe
    probe = shutil.which("ffprobe")
    return probe or "ffprobe"


# Module-level singletons (resolved once at import time)
FFMPEG_PATH: str = get_ffmpeg_path()
FFPROBE_PATH: str = get_ffprobe_path()


def run_ffmpeg(args: list[str], *, check: bool = True, timeout: Optional[int] = None) -> subprocess.CompletedProcess[str]:
    """Run an FFmpeg command with standard error handling.

    Args:
        args: Command arguments *without* the ffmpeg binary itself.
        check: Raise on non-zero return code.
        timeout: Optional timeout in seconds.

    Returns:
        CompletedProcess instance.
    """
    cmd = [FFMPEG_PATH, "-y", *args]
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        logger.error("FFmpeg error: %s", result.stderr)
        raise RuntimeError(f"FFmpeg failed (rc={result.returncode}): {result.stderr[:500]}")
    return result


def run_ffprobe(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run an FFprobe command."""
    cmd = [FFPROBE_PATH, *args]
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed: {result.stderr[:500]}")
    return result


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds."""
    result = run_ffprobe([
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ])
    return float(result.stdout.strip())


def get_video_metadata(video_path: str) -> dict:
    """Get full video metadata as dict."""
    import json
    result = run_ffprobe([
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ])
    return json.loads(result.stdout)


def get_video_resolution(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    result = run_ffprobe([
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        video_path,
    ])
    parts = result.stdout.strip().replace("x", ",").split(",")
    return int(parts[0]), int(parts[1])
