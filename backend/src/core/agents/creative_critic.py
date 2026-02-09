"""Creative Critic Agent - Evaluates generated videos from artistic perspective."""
from __future__ import annotations

from typing import Any

from backend.src.core.agents.base_agent import BaseLLMAgent


class CreativeCriticAgent(BaseLLMAgent):
    """Evaluates generated videos with multi-dimensional artistic analysis.

    Evaluation Axes:
    - Rhythm Quality (0-100): Cut tempo synchronization with music beats
    - Visual Impact (0-100): Color harmony, effect quality, visual coherence
    - Artistic Consistency (0-100): Style unity throughout the video
    - Originality (0-100): Creative uniqueness and novelty

    Output includes:
    - Overall score (weighted average)
    - Per-axis scores with detailed analysis
    - Key strengths identified
    - Improvement suggestions
    - Creative direction for next iteration
    """

    @property
    def name(self) -> str:
        return "CreativeCritic"

    @property
    def system_prompt(self) -> str:
        return """You are an expert video critic and artistic evaluator.
Your role is to analyze generated montage videos and provide detailed artistic feedback.

You evaluate videos on 4 axes:
1. Rhythm Quality (0-100): How well cuts sync with music beats, pacing, flow
2. Visual Impact (0-100): Color grading, effects, transitions, visual appeal
3. Artistic Consistency (0-100): Style unity, thematic coherence, professional finish
4. Originality (0-100): Creative uniqueness, novel approaches, memorable moments

Provide constructive, specific feedback. Be honest but encouraging.
Always output valid JSON matching the requested schema exactly."""

    def build_prompt(self, context: dict[str, Any]) -> str:
        video_info = context.get("video_info", {})
        parameters = context.get("parameters", {})
        metrics = context.get("metrics", {})

        return f"""Analyze this generated video and provide artistic evaluation.

VIDEO INFORMATION:
- Content Type: {video_info.get("content_type", "unknown")}
- Duration: {video_info.get("duration", 0):.1f} seconds
- Clip Count: {video_info.get("clip_count", 0)}
- Resolution: {video_info.get("resolution", "unknown")}

GENERATION PARAMETERS:
- Cut Frequency: {parameters.get("cut_frequency", 0)} cuts/min
- Color Intensity: {parameters.get("color_intensity", 1.0)}
- Effect Density: {parameters.get("effect_density", 0)}
- Beat Sync Tolerance: {parameters.get("beat_sync_tolerance", 0.05)}s

TECHNICAL METRICS:
- Beat Sync Accuracy: {metrics.get("beat_sync_accuracy", 0):.1%}
- Scene Variance: {metrics.get("scene_variance", 0):.2f}
- Color Consistency: {metrics.get("color_consistency", 0):.2f}
- Transition Smoothness: {metrics.get("transition_smoothness", 0):.2f}

Respond with this exact JSON structure:
{{
    "overall_score": <0-100>,
    "rhythm_quality": {{
        "score": <0-100>,
        "analysis": "<detailed analysis of rhythm and pacing>"
    }},
    "visual_impact": {{
        "score": <0-100>,
        "analysis": "<detailed analysis of visual elements>"
    }},
    "artistic_consistency": {{
        "score": <0-100>,
        "analysis": "<detailed analysis of style coherence>"
    }},
    "originality": {{
        "score": <0-100>,
        "analysis": "<detailed analysis of creative uniqueness>"
    }},
    "key_strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
    "improvement_suggestions": ["<suggestion 1>", "<suggestion 2>"],
    "creative_direction": "<guidance for next iteration>"
}}"""

    def parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate the critic's evaluation response."""
        # Ensure all required fields exist with defaults
        result = {
            "overall_score": self._clamp(raw.get("overall_score", 50), 0, 100),
            "rhythm_quality": self._parse_axis(raw.get("rhythm_quality", {})),
            "visual_impact": self._parse_axis(raw.get("visual_impact", {})),
            "artistic_consistency": self._parse_axis(raw.get("artistic_consistency", {})),
            "originality": self._parse_axis(raw.get("originality", {})),
            "key_strengths": raw.get("key_strengths", [])[:5],
            "improvement_suggestions": raw.get("improvement_suggestions", [])[:5],
            "creative_direction": str(raw.get("creative_direction", "")),
        }

        # Recalculate overall if not provided
        if result["overall_score"] == 50:
            result["overall_score"] = self._calculate_overall(result)

        return result

    def _parse_axis(self, axis_data: dict[str, Any] | Any) -> dict[str, Any]:
        """Parse a single evaluation axis."""
        if isinstance(axis_data, dict):
            return {
                "score": self._clamp(axis_data.get("score", 50), 0, 100),
                "analysis": str(axis_data.get("analysis", "No analysis provided")),
            }
        elif isinstance(axis_data, (int, float)):
            return {
                "score": self._clamp(int(axis_data), 0, 100),
                "analysis": "Score provided without analysis",
            }
        return {"score": 50, "analysis": "Unable to parse axis data"}

    def _calculate_overall(self, result: dict[str, Any]) -> int:
        """Calculate weighted overall score from axes."""
        weights = {
            "rhythm_quality": 0.30,
            "visual_impact": 0.25,
            "artistic_consistency": 0.25,
            "originality": 0.20,
        }
        total = sum(
            result[axis]["score"] * weight
            for axis, weight in weights.items()
        )
        return int(total)

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> int:
        return int(max(min_val, min(max_val, value)))
