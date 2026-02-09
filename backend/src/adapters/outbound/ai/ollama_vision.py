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
from pathlib import Path
from typing import Any

import requests

from backend.src.core.entities.analysis_result import FrameAnalysis

logger = logging.getLogger(__name__)


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

    def _analyze_frame_sync(self, frame_path: str) -> FrameAnalysis:
        """Synchronous single-frame analysis (runs in executor)."""
        try:
            image_b64 = self._encode_image(frame_path)
            prompt = self._create_vision_prompt()

            response = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._vision_model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
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
            "Analyze this FPS game screenshot and provide a JSON response "
            "with the following fields:\n\n"
            "{\n"
            '    "kill_log": boolean,\n'
            '    "match_status": string,\n'
            '    "action_intensity": string,\n'
            '    "enemy_visible": boolean,\n'
            '    "ui_elements": string,\n'
            '    "scene_description": string\n'
            "}\n\n"
            "Only respond with valid JSON, no additional text."
        )

    # -- Thinking-model clip selection ----------------------------------

    def _determine_clips_sync(
        self,
        analysis_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            prompt = self._create_thinking_prompt(analysis_results)
            response = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._thinking_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout * 2,
            )
            response.raise_for_status()

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
