"""Multi-model vision adapter wrapping the legacy MultiModelAnalyzer.

Creates several OllamaVisionAdapter instances (one per model) and
combines their results using configurable strategies: ensemble voting,
confidence-based fallback, or specialised task division.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

from backend.src.adapters.outbound.ai.ollama_vision import OllamaVisionAdapter
from backend.src.core.entities.analysis_result import FrameAnalysis

logger = logging.getLogger(__name__)

# Default model list when none is specified in config.
_DEFAULT_MODELS: list[str] = [
    "qwen2-vl:7b",
    "llama3.2-vision",
    "llava:13b",
]


class MultiModelVisionAdapter:
    """Implements VisionAnalysisPort by combining multiple vision models."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        multi_cfg = config.get("multi_model", {})

        self._enabled: bool = multi_cfg.get("enable", False)
        self._strategy: str = multi_cfg.get("strategy", "ensemble")
        self._confidence_threshold: float = multi_cfg.get(
            "confidence_threshold", 0.7
        )

        self._models: list[str] = multi_cfg.get("models", list(_DEFAULT_MODELS))

        # Build one adapter per model, overriding vision_model in each copy.
        self._adapters: dict[str, OllamaVisionAdapter] = {}
        for model_name in self._models:
            model_config = _deep_copy_config(config)
            model_config["ollama"]["vision_model"] = model_name
            self._adapters[model_name] = OllamaVisionAdapter(model_config)

        logger.info(
            "MultiModelVisionAdapter initialised (%d models, strategy=%s): %s",
            len(self._models),
            self._strategy,
            self._models,
        )

    # ------------------------------------------------------------------
    # VisionAnalysisPort interface
    # ------------------------------------------------------------------

    async def analyze_frame(self, frame_path: str) -> FrameAnalysis:
        """Analyse a frame using the configured multi-model strategy."""
        if not self._enabled or len(self._models) <= 1:
            return await self._primary_adapter.analyze_frame(frame_path)

        if self._strategy == "ensemble":
            return await self._ensemble_analysis(frame_path)
        if self._strategy == "confidence":
            return await self._confidence_based_analysis(frame_path)
        if self._strategy == "specialized":
            return await self._specialized_analysis(frame_path)

        # Fallback to ensemble for unknown strategy names.
        return await self._ensemble_analysis(frame_path)

    async def analyze_frames_batch(
        self,
        paths: list[str],
        concurrency: int = 4,
    ) -> list[FrameAnalysis]:
        """Batch-analyse using bounded concurrency."""
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
                out.append(self._default_analysis(paths[idx]))
            else:
                out.append(result)
        return out

    def test_connection(self) -> bool:
        """Test connectivity for *all* underlying adapters."""
        return all(adapter.test_connection() for adapter in self._adapters.values())

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    async def _ensemble_analysis(self, frame_path: str) -> FrameAnalysis:
        """All models analyse in parallel; results combined by majority vote."""
        logger.info("Ensemble analysis with %d models", len(self._models))

        tasks = [
            adapter.analyze_frame(frame_path)
            for adapter in self._adapters.values()
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        valid: list[FrameAnalysis] = [
            r for r in raw_results if isinstance(r, FrameAnalysis)
        ]
        if not valid:
            logger.error("All models failed during ensemble analysis")
            return self._default_analysis(frame_path)

        # Majority vote on categorical fields.
        kill_log = Counter(r.kill_log for r in valid).most_common(1)[0][0]
        action_intensity = Counter(r.action_intensity for r in valid).most_common(1)[0][0]
        match_status = Counter(r.match_status for r in valid).most_common(1)[0][0]

        avg_confidence = sum(r.confidence for r in valid) / len(valid)

        models_used = [
            name
            for name, res in zip(self._models, raw_results)
            if isinstance(res, FrameAnalysis)
        ]

        result = FrameAnalysis(
            frame_path=frame_path,
            timestamp=valid[0].timestamp,
            kill_log=kill_log,
            action_intensity=action_intensity,
            match_status=match_status,
            confidence=avg_confidence,
            enemy_visible=any(r.enemy_visible for r in valid),
            scene_description=valid[0].scene_description,
            ui_elements=valid[0].ui_elements,
            model_used=",".join(models_used),
            metadata={
                "ensemble_votes": len(valid),
                "models_used": models_used,
            },
        )
        logger.info(
            "Ensemble result: kill_log=%s (confidence=%.2f)",
            kill_log,
            avg_confidence,
        )
        return result

    async def _confidence_based_analysis(self, frame_path: str) -> FrameAnalysis:
        """Primary model first; fallback to secondary if confidence is low."""
        primary_name = self._models[0]
        logger.info("Confidence-based analysis: primary=%s", primary_name)

        result = await self._adapters[primary_name].analyze_frame(frame_path)

        if (
            result.confidence < self._confidence_threshold
            and len(self._models) > 1
        ):
            secondary_name = self._models[1]
            logger.info(
                "Low confidence (%.2f < %.2f), running secondary model %s",
                result.confidence,
                self._confidence_threshold,
                secondary_name,
            )
            secondary_result = await self._adapters[secondary_name].analyze_frame(
                frame_path
            )
            if secondary_result.confidence > result.confidence:
                logger.info("Using secondary model result (higher confidence)")
                secondary_result.metadata["fallback_used"] = True
                return secondary_result

            result.metadata["fallback_checked"] = True

        return result

    async def _specialized_analysis(self, frame_path: str) -> FrameAnalysis:
        """Each model handles a specialised aspect of the analysis."""
        logger.info("Specialised analysis with task division")

        tasks = [
            adapter.analyze_frame(frame_path)
            for adapter in self._adapters.values()
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        valid: list[FrameAnalysis] = [
            r for r in raw_results if isinstance(r, FrameAnalysis)
        ]
        if not valid:
            return self._default_analysis(frame_path)

        # Take kill_log from first model (e.g. Qwen2-VL), action_intensity
        # from second, and fall back to first for everything else.
        kill_log = valid[0].kill_log
        action_intensity = valid[1].action_intensity if len(valid) > 1 else valid[0].action_intensity
        match_status = valid[0].match_status
        avg_confidence = sum(r.confidence for r in valid) / len(valid)

        return FrameAnalysis(
            frame_path=frame_path,
            timestamp=valid[0].timestamp,
            kill_log=kill_log,
            action_intensity=action_intensity,
            match_status=match_status,
            confidence=avg_confidence,
            enemy_visible=any(r.enemy_visible for r in valid),
            scene_description=valid[0].scene_description,
            ui_elements=valid[0].ui_elements,
            model_used=",".join(m for m in self._models),
            metadata={"specialized": True},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _primary_adapter(self) -> OllamaVisionAdapter:
        return self._adapters[self._models[0]]

    @staticmethod
    def _default_analysis(frame_path: str) -> FrameAnalysis:
        return FrameAnalysis(
            frame_path=frame_path,
            confidence=0.0,
            metadata={"error": "all_models_failed"},
        )

    def get_model_stats(self) -> dict[str, Any]:
        """Return diagnostic information about configured models."""
        return {
            "enabled": self._enabled,
            "strategy": self._strategy,
            "models": list(self._models),
            "model_count": len(self._models),
        }


# ------------------------------------------------------------------
# Module-private utilities
# ------------------------------------------------------------------

def _deep_copy_config(config: dict[str, Any]) -> dict[str, Any]:
    """Shallow-copy the top-level dict and the ``ollama`` sub-dict so
    mutations do not leak across adapter instances.
    """
    copy = dict(config)
    copy["ollama"] = dict(config["ollama"])
    return copy
