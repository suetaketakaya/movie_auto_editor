"""Unit tests for GeneralPlugin and registry fallback behavior."""
from __future__ import annotations

import pytest

from backend.src.application.plugins.base_content_plugin import (
    ContentPlugin,
    DirectorConfig,
    QualityMetrics,
)
from backend.src.application.plugins.general_plugin import GeneralPlugin
from backend.src.application.plugins.plugin_registry import PluginRegistry
from backend.src.core.entities.analysis_result import FrameAnalysis
from backend.src.core.entities.content_type import ContentType


class TestGeneralPlugin:
    """Tests for GeneralPlugin interface methods."""

    @pytest.fixture
    def plugin(self) -> GeneralPlugin:
        return GeneralPlugin()

    def test_name(self, plugin: GeneralPlugin):
        assert plugin.name == "general"

    def test_display_name(self, plugin: GeneralPlugin):
        assert plugin.display_name == "General"

    def test_is_content_plugin(self, plugin: GeneralPlugin):
        assert isinstance(plugin, ContentPlugin)

    def test_get_director_config_returns_defaults(self, plugin: GeneralPlugin):
        config = plugin.get_director_config()
        assert isinstance(config, DirectorConfig)
        assert config.min_clip_length == 3.0
        assert config.max_clip_length == 15.0
        assert config.target_duration == 180.0

    def test_get_quality_metrics_relaxed(self, plugin: GeneralPlugin):
        metrics = plugin.get_quality_metrics()
        assert isinstance(metrics, QualityMetrics)
        assert metrics.min_score == 50.0
        assert metrics.required_clip_types == []
        assert metrics.max_duration_deviation == 60.0
        assert metrics.min_clips == 1

    def test_get_vision_prompt_override_returns_none(self, plugin: GeneralPlugin):
        assert plugin.get_vision_prompt_override() is None

    def test_preprocess_passes_through(self, plugin: GeneralPlugin, sample_analyses):
        result = plugin.preprocess(sample_analyses)
        assert result is sample_analyses

    def test_postprocess_clips_sorted_by_score(self, plugin: GeneralPlugin, sample_clips):
        result = plugin.postprocess_clips(sample_clips)
        scores = [c.score.value for c in result]
        assert scores == sorted(scores, reverse=True)


class TestPluginRegistryFallback:
    """Tests for plugin registry fallback to GeneralPlugin."""

    def test_create_default_includes_general(self):
        registry = PluginRegistry.create_default()
        plugins = registry.list_plugins()
        names = [p["name"] for p in plugins]
        assert "general" in names
        assert "fps_montage" in names

    def test_get_or_default_returns_fps_for_fps(self):
        registry = PluginRegistry.create_default()
        plugin = registry.get_or_default(ContentType.FPS_MONTAGE)
        assert plugin.name == "fps_montage"

    def test_get_or_default_returns_general_for_general(self):
        registry = PluginRegistry.create_default()
        plugin = registry.get_or_default(ContentType.GENERAL)
        assert plugin.name == "general"

    def test_get_or_default_falls_back_to_general(self):
        registry = PluginRegistry.create_default()
        plugin = registry.get_or_default(ContentType.MAD_AMV)
        assert plugin.name == "general"

    def test_get_or_default_falls_back_for_all_unregistered(self):
        registry = PluginRegistry.create_default()
        for ct in [ContentType.SPORTS_HIGHLIGHT, ContentType.ANIME_PV, ContentType.MUSIC_VIDEO]:
            plugin = registry.get_or_default(ct)
            assert plugin.name == "general"

    def test_get_returns_none_for_unregistered(self):
        registry = PluginRegistry.create_default()
        assert registry.get(ContentType.MAD_AMV) is None
