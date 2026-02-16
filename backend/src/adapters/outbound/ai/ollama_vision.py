"""Adapter wrapping the legacy OllamaClient for the VisionAnalysisPort.

Translates between the legacy dict-based Ollama API calls and the
hexagonal FrameAnalysis entity used by the core domain.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

from backend.src.core.entities.analysis_result import FrameAnalysis

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0  # seconds


class OllamaVisionAdapter:
    """Implements VisionAnalysisPort by calling the Ollama vision API."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: dict[str, Any]) -> None:
        ollama_cfg = config["ollama"]
        self._base_url: str = ollama_cfg["base_url"]
        self._vision_model: str = ollama_cfg["vision_model"]
        self._thinking_model: str = ollama_cfg["thinking_model"]
        self._timeout: int = ollama_cfg.get("timeout", 120)
        self._config = config
        logger.info(
            "OllamaVisionAdapter initialised (model=%s, url=%s)",
            self._vision_model,
            self._base_url,
        )

    # ------------------------------------------------------------------
    # VisionAnalysisPort interface
    # ------------------------------------------------------------------

    async def analyze_frame(self, frame_path: str) -> FrameAnalysis:
        """Analyse a single frame image via Ollama vision model.

        The heavy HTTP call is offloaded to a thread so we never block
        the event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._analyze_frame_sync, frame_path)

    async def analyze_frames_batch(
        self,
        paths: list[str],
        concurrency: int = 4,
    ) -> list[FrameAnalysis]:
        """Analyse many frames with bounded concurrency."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _limited(path: str) -> FrameAnalysis:
            async with semaphore:
                return await self.analyze_frame(path)

        results = await asyncio.gather(
            *[_limited(p) for p in paths],
            return_exceptions=True,
        )

        out: list[FrameAnalysis] = []
        for idx, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error("Batch frame %s failed: %s", paths[idx], result)
                out.append(self._error_analysis(paths[idx], str(result)))
            else:
                out.append(result)
        return out

    def test_connection(self) -> bool:
        """Return *True* if the Ollama server is reachable."""
        try:
            resp = requests.get(
                f"{self._base_url}/api/tags",
                timeout=5,
            )
            resp.raise_for_status()
            logger.info("Ollama connection successful")
            return True
        except Exception as exc:
            logger.error("Ollama connection failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Legacy clip-determination helpers (delegated from LLMReasoningPort
    # implementations but kept here so the adapter stays self-contained
    # when used standalone).
    # ------------------------------------------------------------------

    async def determine_clips(
        self,
        analysis_results: list[FrameAnalysis],
    ) -> list[dict[str, Any]]:
        """Use the thinking model to select highlight clips."""
        loop = asyncio.get_running_loop()
        legacy_dicts = [a.to_legacy_dict() for a in analysis_results]
        return await loop.run_in_executor(
            None, self._determine_clips_sync, legacy_dicts
        )

    # ------------------------------------------------------------------
    # Internal / synchronous helpers
    # ------------------------------------------------------------------

    def _request_with_retry(
        self, url: str, payload: dict, timeout: int
    ) -> requests.Response:
        """Make an HTTP request with exponential backoff retry."""
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Ollama request attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, exc, backoff,
                )
                time.sleep(backoff)
            except requests.exceptions.HTTPError as exc:
                # Don't retry on 4xx errors
                if exc.response is not None and 400 <= exc.response.status_code < 500:
                    raise
                last_exc = exc
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Ollama request attempt %d/%d failed (HTTP %s), retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, exc, backoff,
                )
                time.sleep(backoff)
        raise last_exc  # type: ignore[misc]

    def _analyze_frame_sync(self, frame_path: str) -> FrameAnalysis:
        """Synchronous single-frame analysis (runs in executor)."""
        try:
            image_b64 = self._encode_image(frame_path)
            prompt = self._create_vision_prompt()

            response = self._request_with_retry(
                f"{self._base_url}/api/generate",
                {
                    "model": self._vision_model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            raw_text = response.json().get("response", "{}")

            try:
                parsed: dict[str, Any] = json.loads(raw_text)
            except json.JSONDecodeError:
                parsed = {
                    "kill_log": False,
                    "match_status": "unknown",
                    "action_intensity": "low",
                }

            frame_name = Path(frame_path).name
            timestamp = self._extract_timestamp(frame_name)

            return FrameAnalysis(
                frame_path=frame_path,
                timestamp=timestamp,
                kill_log=bool(parsed.get("kill_log", False)),
                match_status=str(parsed.get("match_status", "unknown")),
                action_intensity=str(parsed.get("action_intensity", "low")),
                enemy_visible=bool(parsed.get("enemy_visible", False)),
                scene_description=str(parsed.get("scene_description", "")),
                confidence=float(parsed.get("confidence", 0.0)),
                ui_elements=str(parsed.get("ui_elements", "")),
                kill_count=int(parsed.get("kill_count", 0)),
                enemy_count=int(parsed.get("enemy_count", 0)),
                visual_quality=str(parsed.get("visual_quality", "normal")),
                model_used=self._vision_model,
                raw_response=raw_text,
            )

        except Exception as exc:
            logger.error("Error analysing frame %s: %s", frame_path, exc)
            return self._error_analysis(frame_path, str(exc))

    # -- Prompt creation ------------------------------------------------

    @staticmethod
    def _create_vision_prompt() -> str:
        return (
            "You are an expert FPS game footage analyst. Analyze this game screenshot "
            "carefully, paying attention to the HUD elements (kill feed, minimap, "
            "health/armor bars, ammo counter, scoreboard), player perspective, and "
            "on-screen action.\n\n"
            "Provide a JSON response with these fields:\n\n"
            "{\n"
            '    "kill_log": boolean (true if kill feed shows a recent kill by the player),\n'
            '    "kill_count": integer (number of kills visible in kill feed for the player, 0 if none),\n'
            '    "match_status": string ("normal", "clutch", "victory", "defeat", "overtime"),\n'
            '    "action_intensity": string ("very_high", "high", "medium", "low"),\n'
            '    "enemy_visible": boolean (true if enemy players are visible on screen),\n'
            '    "enemy_count": integer (number of visible enemy players, 0 if none),\n'
            '    "ui_elements": string (describe visible HUD elements),\n'
            '    "visual_quality": string ("cinematic", "high", "normal", "low"),\n'
            '    "scene_description": string (brief description of the action),\n'
            '    "confidence": float (0.0 to 1.0, your confidence in this analysis)\n'
            "}\n\n"
            "Guidelines:\n"
            "- action_intensity: very_high = active multi-kill/clutch, high = active combat, "
            "medium = positioning/utility, low = idle/walking\n"
            "- visual_quality: cinematic = dramatic angle/lighting, high = clear action shot, "
            "normal = standard gameplay, low = obscured/dark\n"
            "- Be precise about kill_count: count individual kill entries in the kill feed\n"
            "- confidence: rate how certain you are about the analysis overall\n\n"
            "Only respond with valid JSON, no additional text."
        )

    # -- Thinking-model clip selection ----------------------------------

    def _determine_clips_sync(
        self,
        analysis_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            prompt = self._create_thinking_prompt(analysis_results)
            response = self._request_with_retry(
                f"{self._base_url}/api/generate",
                {
                    "model": self._thinking_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout * 2,
            )

            try:
                data = json.loads(response.json().get("response", "{}"))
                clips: list[dict[str, Any]] = data.get("clips", [])
            except json.JSONDecodeError:
                logger.error("Failed to parse thinking model response")
                clips = self._fallback_clip_detection(analysis_results)

            logger.info("Determined %d highlight clips", len(clips))
            return clips

        except Exception as exc:
            logger.error("Error determining clips: %s", exc)
            return self._fallback_clip_detection(analysis_results)

    @staticmethod
    def _create_thinking_prompt(analysis_results: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for r in analysis_results:
            ts = r.get("timestamp", 0)
            kill = r.get("kill_log", False)
            action = r.get("action_intensity", "low")
            lines.append(f"[{ts:.1f}s] Kill: {kill}, Action: {action}")
        timeline = "\n".join(lines)
        return (
            "You are a video editing assistant. Based on the following FPS "
            "game frame analysis timeline, identify the best highlight clips.\n\n"
            f"Timeline:\n{timeline}\n\n"
            "Criteria:\n"
            "1. Scenes with kill_log = true\n"
            "2. Scenes with action_intensity = \"high\"\n"
            "3. Include 5-10 seconds context before/after\n"
            "4. Min clip: 10 s, Max clip: 30 s\n"
            "5. No overlapping clips\n\n"
            "Respond with JSON:\n"
            '{"clips": [{"start": 10.0, "end": 25.0, "reason": "..."}]}\n\n'
            "Only respond with valid JSON."
        )

    @staticmethod
    def _fallback_clip_detection(
        analysis_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rule-based fallback grouping kill timestamps into clips."""
        kill_ts = [
            r.get("timestamp", 0)
            for r in analysis_results
            if r.get("kill_log", False)
        ]
        if not kill_ts:
            return []

        clips: list[dict[str, Any]] = []
        start = kill_ts[0] - 5
        last = kill_ts[0]

        for ts in kill_ts[1:]:
            if ts - last > 10:
                clips.append(
                    {
                        "start": max(0, start),
                        "end": last + 5,
                        "reason": "Kill sequence",
                    }
                )
                start = ts - 5
            last = ts

        clips.append(
            {"start": max(0, start), "end": last + 5, "reason": "Kill sequence"}
        )
        logger.info("Fallback detection found %d clips", len(clips))
        return clips

    # -- Utilities ------------------------------------------------------

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")

    @staticmethod
    def _extract_timestamp(frame_name: str) -> float:
        """Extract timestamp from filenames like ``frame_000001_t12.34s.jpg``."""
        try:
            match = re.search(r"_t([\d.]+)s\.", frame_name)
            if match:
                return float(match.group(1))
        except Exception as exc:
            logger.warning("Could not extract timestamp from %s: %s", frame_name, exc)
        return 0.0

    # -- Error helpers --------------------------------------------------

    def _error_analysis(self, frame_path: str, error_msg: str) -> FrameAnalysis:
        return FrameAnalysis(
            frame_path=frame_path,
            timestamp=self._extract_timestamp(Path(frame_path).name),
            kill_log=False,
            match_status="unknown",
            action_intensity="low",
            confidence=0.0,
            model_used=self._vision_model,
            raw_response=None,
            metadata={"error": error_msg},
        )
