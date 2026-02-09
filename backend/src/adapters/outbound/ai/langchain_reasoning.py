"""
LangChain-based LLM reasoning adapter.
Implements LLMReasoningPort for clip selection and quality evaluation.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import requests

from backend.src.core.value_objects.quality_score import QualityScore

logger = logging.getLogger(__name__)


class LangChainReasoningAdapter:
    """LLM reasoning via Ollama (with optional LangChain integration)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "deepseek-r1:8b",
        timeout: int = 120,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def reason_about_clips(self, analysis_summary: str) -> list[dict]:
        """Use LLM to reason about which clips to select."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._reason_clips_sync, analysis_summary
        )

    def _reason_clips_sync(self, analysis_summary: str) -> list[dict]:
        prompt = f"""You are a video editing assistant. Based on the following frame analysis timeline, identify the best highlight clips.

Timeline:
{analysis_summary}

Criteria:
1. Scenes with kills or high action intensity
2. Include 5-10 seconds context before and after
3. Clip length: 10-30 seconds
4. No overlapping clips

Respond with JSON:
{{"clips": [{{"start": 10.0, "end": 25.0, "reason": "description"}}]}}

Only valid JSON, no additional text."""

        try:
            resp = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = json.loads(resp.json().get("response", "{}"))
            return data.get("clips", [])
        except Exception as e:
            logger.error("LLM reasoning failed: %s", e)
            return []

    async def evaluate_quality(self, description: str) -> QualityScore:
        """Use LLM to evaluate video quality from a description."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._evaluate_quality_sync, description
        )

    def _evaluate_quality_sync(self, description: str) -> QualityScore:
        prompt = f"""Rate the quality of this video edit on a scale of 0-100.

Description:
{description}

Respond with JSON: {{"score": <number>, "reasoning": "<text>"}}
Only valid JSON."""

        try:
            resp = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = json.loads(resp.json().get("response", "{}"))
            score = float(data.get("score", 50))
            return QualityScore(value=score)
        except Exception as e:
            logger.error("Quality evaluation failed: %s", e)
            return QualityScore(value=50.0)

    async def suggest_creative_direction(self, context: dict) -> dict:
        """Use LLM to suggest creative direction based on content analysis."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._suggest_direction_sync, context
        )

    def _suggest_direction_sync(self, context: dict) -> dict:
        prompt = f"""Based on this video analysis context, suggest creative direction.

Context:
{json.dumps(context, indent=2)}

Respond with JSON:
{{
    "pacing": "fast" or "medium" or "slow",
    "color_preset": "cinematic" or "vibrant" or "warm" or "cool",
    "transition_style": "fade" or "cut" or "wipe",
    "music_mood": "energetic" or "dramatic" or "chill",
    "reasoning": "<text>"
}}"""

        try:
            resp = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return json.loads(resp.json().get("response", "{}"))
        except Exception as e:
            logger.error("Creative direction suggestion failed: %s", e)
            return {
                "pacing": "medium",
                "color_preset": "cinematic",
                "transition_style": "fade",
                "music_mood": "energetic",
            }
