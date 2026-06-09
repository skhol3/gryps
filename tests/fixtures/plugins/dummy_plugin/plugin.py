from __future__ import annotations


class DummyPlugin:
    """Minimal test plugin for PluginRegistry loading tests."""

    def process(self) -> str:
        return "dummy_processed"
