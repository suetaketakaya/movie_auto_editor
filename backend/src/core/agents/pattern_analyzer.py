"""Pattern Analyzer Agent - Discovers success patterns from historical data."""
from __future__ import annotations

from typing import Any

from backend.src.core.agents.base_agent import BaseLLMAgent


class PatternAnalyzerAgent(BaseLLMAgent):
    """Analyzes historical video generation data to discover success patterns.

    Responsibilities:
    - Identify common parameters in top-performing videos
    - Find failure patterns in low-performing videos
    - Discover parameter correlations (e.g., "cut_frequency + saturation")
    - Suggest unexplored promising parameter combinations

    Output includes:
    - Success patterns (Top N video commonalities)
    - Failure patterns (Bottom N video commonalities)
    - Parameter correlations with strength indicators
    - Exploration suggestions for untested regions
    """

    @property
    def name(self) -> str:
        return "PatternAnalyzer"

    @property
    def system_prompt(self) -> str:
        return """You are an expert data analyst specializing in creative parameter optimization.
Your role is to analyze historical video generation results and discover actionable patterns.

Focus on:
1. SUCCESS PATTERNS: What parameters do high-performing videos share?
2. FAILURE PATTERNS: What parameter combinations lead to poor results?
3. CORRELATIONS: Which parameters influence each other?
4. UNEXPLORED REGIONS: What promising parameter combinations haven't been tried?

Be specific with numbers and parameter names.
Always output valid JSON matching the requested schema exactly."""

    def build_prompt(self, context: dict[str, Any]) -> str:
        history = context.get("history", [])
        parameter_space = context.get("parameter_space", {})
        content_type = context.get("content_type", "general")

        # Format history for analysis
        history_text = self._format_history(history)
        space_text = self._format_parameter_space(parameter_space)

        return f"""Analyze the video generation history and identify patterns.

CONTENT TYPE: {content_type}

PARAMETER SPACE:
{space_text}

GENERATION HISTORY (sorted by reward, highest first):
{history_text}

Based on this data, identify:
1. What parameters are common in the TOP 5 performing videos?
2. What parameters are common in the BOTTOM 5 performing videos?
3. What correlations exist between parameters and performance?
4. What unexplored parameter combinations might be worth trying?

Respond with this exact JSON structure:
{{
    "success_patterns": [
        {{
            "pattern": "<description of successful pattern>",
            "parameters": {{"<param>": <typical_value>}},
            "confidence": <0.0-1.0>,
            "occurrences": <count>
        }}
    ],
    "failure_patterns": [
        {{
            "pattern": "<description of failure pattern>",
            "parameters": {{"<param>": <typical_value>}},
            "confidence": <0.0-1.0>,
            "occurrences": <count>
        }}
    ],
    "correlations": [
        {{
            "parameters": ["<param1>", "<param2>"],
            "relationship": "<positive|negative|nonlinear>",
            "strength": <0.0-1.0>,
            "insight": "<explanation>"
        }}
    ],
    "exploration_suggestions": [
        {{
            "parameters": {{"<param>": <suggested_value>}},
            "rationale": "<why this might work>",
            "expected_improvement": "<low|medium|high>"
        }}
    ],
    "summary": "<overall analysis summary>"
}}"""

    def _format_history(self, history: list[dict[str, Any]]) -> str:
        """Format generation history for the prompt."""
        if not history:
            return "No history available yet."

        lines = []
        for i, entry in enumerate(history[:20], 1):  # Limit to top 20
            params = entry.get("parameters", {})
            reward = entry.get("reward", 0)
            quality = entry.get("quality_score", 0)
            lines.append(
                f"{i}. Reward: {reward:.2f}, Quality: {quality:.0f}, "
                f"Params: {self._format_params(params)}"
            )
        return "\n".join(lines)

    def _format_params(self, params: dict[str, Any]) -> str:
        """Format parameters compactly."""
        key_params = ["cut_frequency", "color_intensity", "effect_density",
                      "beat_sync_tolerance", "saturation", "contrast"]
        parts = []
        for key in key_params:
            if key in params:
                parts.append(f"{key}={params[key]}")
        return ", ".join(parts) if parts else str(params)

    def _format_parameter_space(self, space: dict[str, Any]) -> str:
        """Format parameter space definition."""
        if not space:
            return "Default parameter space"
        lines = []
        for param, bounds in space.items():
            if isinstance(bounds, tuple) and len(bounds) == 2:
                lines.append(f"- {param}: [{bounds[0]}, {bounds[1]}]")
            else:
                lines.append(f"- {param}: {bounds}")
        return "\n".join(lines)

    def parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate the pattern analysis response."""
        return {
            "success_patterns": self._parse_patterns(raw.get("success_patterns", [])),
            "failure_patterns": self._parse_patterns(raw.get("failure_patterns", [])),
            "correlations": self._parse_correlations(raw.get("correlations", [])),
            "exploration_suggestions": self._parse_suggestions(
                raw.get("exploration_suggestions", [])
            ),
            "summary": str(raw.get("summary", "No summary provided")),
        }

    def _parse_patterns(self, patterns: list[Any]) -> list[dict[str, Any]]:
        """Parse pattern list with validation."""
        result = []
        for p in patterns[:5]:  # Limit to 5
            if isinstance(p, dict):
                result.append({
                    "pattern": str(p.get("pattern", "")),
                    "parameters": p.get("parameters", {}),
                    "confidence": float(p.get("confidence", 0.5)),
                    "occurrences": int(p.get("occurrences", 1)),
                })
        return result

    def _parse_correlations(self, correlations: list[Any]) -> list[dict[str, Any]]:
        """Parse correlation list with validation."""
        result = []
        for c in correlations[:5]:
            if isinstance(c, dict):
                result.append({
                    "parameters": list(c.get("parameters", []))[:2],
                    "relationship": str(c.get("relationship", "unknown")),
                    "strength": float(c.get("strength", 0.5)),
                    "insight": str(c.get("insight", "")),
                })
        return result

    def _parse_suggestions(self, suggestions: list[Any]) -> list[dict[str, Any]]:
        """Parse exploration suggestions with validation."""
        result = []
        for s in suggestions[:3]:
            if isinstance(s, dict):
                result.append({
                    "parameters": s.get("parameters", {}),
                    "rationale": str(s.get("rationale", "")),
                    "expected_improvement": str(s.get("expected_improvement", "medium")),
                })
        return result
