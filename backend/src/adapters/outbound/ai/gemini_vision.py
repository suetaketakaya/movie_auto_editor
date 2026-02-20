"""Adapter wrapping Google Gemini 2.0 Flash for the VisionAnalysisPort.

Uses the google-genai SDK to analyse video frames via the
Gemini Vision API.  Drop-in replacement for OllamaVisionAdapter.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from backend.src.core.entities.analysis_result import FrameAnalysis

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0


class GeminiVisionAdapter:
    """Implements VisionAnalysisPort by calling the Gemini Vision API."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: dict[str, Any]) -> None:
        gemini_cfg = config["gemini"]
        self._api_key: str = gemini_cfg["api_key"]
        self._vision_model: str = gemini_cfg.get("vision_model", "gemini-2.0-flash")
        self._timeout: int = gemini_cfg.get("timeout", 60)
        self._config = config

        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when VISION_BACKEND=gemini. "
                "Get one at https://aistudio.google.com/apikey"
            )

        from google import genai

        self._client = genai.Client(api_key=self._api_key)

        logger.info(
            "GeminiVisionAdapter initialised (model=%s)",
            self._vision_model,
        )

    # ------------------------------------------------------------------
    # VisionAnalysisPort interface
    # ------------------------------------------------------------------

    async def analyze_frame(self, frame_path: str) -> FrameAnalysis:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._analyze_frame_sync, frame_path)

    async def analyze_frames_batch(
        self,
        paths: list[str],
        concurrency: int = 4,
    ) -> list[FrameAnalysis]:
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
        try:
            from google.genai import types
            self._client.models.generate_content(
                model=self._vision_model,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=5),
            )
            logger.info("Gemini connection successful")
            return True
        except Exception as exc:
            logger.error("Gemini connection failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Clip determination (same logic as Ollama adapter)
    # ------------------------------------------------------------------

    async def determine_clips(
        self,
        analysis_results: list[FrameAnalysis],
    ) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        legacy_dicts = [a.to_legacy_dict() for a in analysis_results]
        return await loop.run_in_executor(
            None, self._determine_clips_sync, legacy_dicts
        )

    # ------------------------------------------------------------------
    # Internal / synchronous helpers
    # ------------------------------------------------------------------

    def _analyze_frame_sync(self, frame_path: str) -> FrameAnalysis:
        try:
            image_part = self._load_image(frame_path)
            prompt = self._create_vision_prompt()

            response = self._generate_with_retry(prompt, image_part)
            raw_text = response.text

            parsed = self._extract_json(raw_text)

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

    def _generate_with_retry(self, prompt: str, image_part: Any) -> Any:
        from google.genai import types

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=self._vision_model,
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                return response
            except Exception as exc:
                last_exc = exc
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Gemini request attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, exc, backoff,
                )
                time.sleep(backoff)
        raise last_exc  # type: ignore[misc]

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
            from google.genai import types

            prompt = self._create_thinking_prompt(analysis_results)
            response = self._client.models.generate_content(
                model=self._vision_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            try:
                data = json.loads(response.text)
                clips: list[dict[str, Any]] = data.get("clips", [])
            except json.JSONDecodeError:
                logger.error("Failed to parse Gemini thinking response")
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
    def _load_image(image_path: str) -> Any:
        from PIL import Image
        return Image.open(image_path)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {
            "kill_log": False,
            "match_status": "unknown",
            "action_intensity": "low",
        }

    @staticmethod
    def _extract_timestamp(frame_name: str) -> float:
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
