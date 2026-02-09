"""
Plugin registry for content-type plugins.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.src.application.plugins.base_content_plugin import ContentPlugin
from backend.src.core.entities.content_type import ContentType

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry that maps ContentType to plugin instances."""

    def __init__(self):
        self._plugins: dict[str, ContentPlugin] = {}

    def register(self, plugin: ContentPlugin) -> None:
        """Register a plugin."""
        self._plugins[plugin.name] = plugin
        logger.info("Registered plugin: %s (%s)", plugin.name, plugin.display_name)

    def get(self, content_type: ContentType) -> Optional[ContentPlugin]:
        """Get plugin for content type. Returns None if not registered."""
        return self._plugins.get(content_type.value)

    def get_or_default(self, content_type: ContentType) -> ContentPlugin:
        """Get plugin for content type, falling back to general plugin."""
        plugin = self.get(content_type)
        if plugin is None:
            plugin = self._plugins.get("general")
        if plugin is None:
            raise ValueError(
                f"No plugin found for {content_type.value} and no general fallback registered"
            )
        return plugin

    def list_plugins(self) -> list[dict[str, str]]:
        """List all registered plugins."""
        return [
            {"name": p.name, "display_name": p.display_name}
            for p in self._plugins.values()
        ]

    @staticmethod
    def create_default() -> PluginRegistry:
        """Create registry with all built-in plugins."""
        registry = PluginRegistry()

        from backend.src.application.plugins.fps_montage_plugin import FPSMontagePlugin
        from backend.src.application.plugins.general_plugin import GeneralPlugin
        registry.register(FPSMontagePlugin())
        registry.register(GeneralPlugin())

        # Future plugins:
        # registry.register(MADAMVPlugin())
        # registry.register(SportsHighlightPlugin())
        # registry.register(AnimePVPlugin())
        # registry.register(MusicVideoPlugin())

        return registry
