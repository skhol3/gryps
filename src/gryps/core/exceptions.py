from __future__ import annotations


class GrypsError(Exception):
    """Base exception for all Gryps errors."""


class PluginLoadError(GrypsError):
    """Raised when a plugin cannot be loaded or imported."""


class PluginValidationError(GrypsError):
    """Raised when a plugin manifest fails validation."""


class ConfigError(GrypsError):
    """Raised when configuration is invalid or missing."""
