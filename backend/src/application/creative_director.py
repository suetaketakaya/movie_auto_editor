"""
Creative Director - coordinates the 3-director system.
Manages pacing, visual style, and audio decisions.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from backend.src.application.plugins.base_content_plugin import ContentPlugin, DirectorConfig
from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.clip import Clip
from backend.src.core.entities.creative_direction import CreativeDirection
from backend.src.core.services.clip_scorer import ClipScorer
from backend.src.core.services.composition_planner import CompositionPlanner
from backend.src.core.services.highlight_detector import HighlightDetector

logger = logging.getLogger(__name__)


@dataclass
class DirectorDecisions:
    """Output of the creative director system."""
    clips: list[Clip] = field(default_factory=list)
    hook_clip: Optional[Clip] = None
    engagement_curve: dict = field(default_factory=dict)
    variety_analysis: dict = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    multi_events: list[dict] = field(default_factory=list)
    clutch_moments: list[dict] = field(default_factory=list)
    momentum_shifts: list[dict] = field(default_factory=list)


class CreativeDirector:
    """Coordinates highlight detection, composition planning, and scoring.

    The three 'directors':
    1. Highlight Director (HighlightDetector) - finds the best moments
    2. Composition Director (CompositionPlanner) - plans pacing and structure
    3. Scoring Director (ClipScorer) - predicts engagement
    """

    def __init__(self, config: Optional[DirectorConfig] = None):
        self._config = config or DirectorConfig()
        self._highlight_detector = HighlightDetector()
        self._composition_planner = CompositionPlanner(
            target_duration=self._config.target_duration,
            min_clip_length=self._config.min_clip_length,
            max_clip_length=self._config.max_clip_length,
            optimal_pace=self._config.pacing_variation * 10,
        )
        self._clip_scorer = ClipScorer()

    def direct(
        self,
        analyses: list[FrameAnalysis],
        plugin: Optional[ContentPlugin] = None,
    ) -> DirectorDecisions:
        """Run the full creative direction pipeline."""
        logger.info("Creative direction starting with %d analyses", len(analyses))

        # 1. Plugin preprocessing
        if plugin:
            analyses = plugin.preprocess(analyses)

        # 2. Highlight Director: excitement + event detection
        enhanced = self._highlight_detector.analyze_excitement_levels(analyses)
        multi_events = self._highlight_detector.detect_multi_events(enhanced)
        clutch_moments = self._highlight_detector.detect_clutch_moments(enhanced)
        momentum_shifts = self._highlight_detector.analyze_momentum_shifts(enhanced)

        logger.info(
            "Detected: %d multi-events, %d clutch moments, %d momentum shifts",
            len(multi_events), len(clutch_moments), len(momentum_shifts),
        )

        # 3. Suggest highlights
        highlights = self._highlight_detector.suggest_highlights(
            enhanced, multi_events, clutch_moments
        )

        # 4. Plugin post-processing
        if plugin:
            highlights = plugin.postprocess_clips(highlights)

        # 5. Composition Director: optimize
        optimized = self._composition_planner.optimize_clips(highlights, enhanced)

        # 6. Hook intro
        hook = self._composition_planner.create_hook_intro(optimized)

        # 7. Scoring Director: engagement analysis
        engagement = self._composition_planner.analyze_engagement_curve(optimized)
        variety = self._highlight_detector.analyze_variety(optimized)
        suggestions = self._clip_scorer.suggest_improvements(optimized, enhanced)

        logger.info(
            "Creative direction complete: %d clips, total %.1fs",
            len(optimized),
            sum(c.duration for c in optimized),
        )

        return DirectorDecisions(
            clips=optimized,
            hook_clip=hook,
            engagement_curve=engagement,
            variety_analysis=variety,
            suggestions=suggestions,
            multi_events=multi_events,
            clutch_moments=clutch_moments,
            momentum_shifts=momentum_shifts,
        )
