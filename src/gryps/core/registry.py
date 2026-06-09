from __future__ import annotations

import hashlib
import importlib
import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gryps.core.exceptions import PluginLoadError, PluginValidationError

_SCALAR_BOOL = {
    "true": True,
    "yes": True,
    "on": True,
    "false": False,
    "no": False,
    "off": False,
}


@dataclass(frozen=True)
class PluginManifest:
    """Parsed metadata from a ``plugin.yaml`` file."""

    name: str
    version: str
    entrypoint: str
    class_name: str
    type: str = ""
    directory: Path = Path()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginInfo:
    """Registry entry for a discovered and loaded plugin."""

    manifest: PluginManifest
    directory: Path
    loaded_class: type | None = None


class PluginRegistry:
    """Discovers, validates and loads plugins from filesystem directories.

    Each plugin directory must contain a ``plugin.yaml`` manifest with at
    least ``name``, ``version``, ``entrypoint`` and ``class`` fields.

    Typical usage::

        registry = PluginRegistry(roots=["plugins/", "preprocessors/"])
        registry.discover()
        for name, info in registry.plugins.items():
            obj = info.loaded_class()
    """

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        self._roots: list[Path] = [Path(r).resolve() for r in (roots or [])]
        self._plugins: dict[str, PluginInfo] = {}

    @property
    def plugins(self) -> dict[str, PluginInfo]:
        """Return a snapshot of discovered plugins."""
        return dict(self._plugins)

    def add_root(self, root: str | Path) -> None:
        """Register an additional plugin root directory."""
        resolved = Path(root).resolve()
        if resolved not in self._roots:
            self._roots.append(resolved)

    def scan(self) -> list[PluginManifest]:
        """Find and parse all ``plugin.yaml`` manifests under registered roots.

        Does **not** validate or load — use ``discover()`` for the full
        pipeline.
        """
        manifests: list[PluginManifest] = []
        for root in self._roots:
            if not root.is_dir():
                continue
            for yaml_path in sorted(root.rglob("plugin.yaml")):
                manifest = _load_manifest(yaml_path)
                manifests.append(manifest)
        return manifests

    def discover(self) -> dict[str, PluginInfo]:
        """Run the full pipeline: scan → validate → load.

        Returns a dict mapping plugin name to ``PluginInfo``.
        Raises ``PluginLoadError`` on duplicate names or loading failures.
        """
        manifests = self.scan()
        self._plugins = {}
        seen: dict[str, Path] = {}
        for manifest in manifests:
            _validate_manifest(manifest)
            if manifest.name in seen:
                raise PluginLoadError(
                    f"Duplicate plugin name '{manifest.name}': "
                    f"found in '{manifest.directory}' and "
                    f"'{seen[manifest.name]}'"
                )
            seen[manifest.name] = manifest.directory
            cls = _load_entrypoint(manifest)
            info = PluginInfo(
                manifest=manifest,
                directory=manifest.directory,
                loaded_class=cls,
            )
            self._plugins[manifest.name] = info
        return dict(self._plugins)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_manifest(yaml_path: Path) -> PluginManifest:
    raw = _parse_manifest_yaml(yaml_path)
    return PluginManifest(
        name=str(raw.get("name", "")),
        version=str(raw.get("version", "")),
        entrypoint=str(raw.get("entrypoint", "")),
        class_name=str(raw.get("class", "")),
        type=str(raw.get("type", "")),
        directory=yaml_path.parent,
        raw=raw,
    )


def _validate_manifest(manifest: PluginManifest) -> None:
    missing: list[str] = []
    if not manifest.name:
        missing.append("name")
    if not manifest.version:
        missing.append("version")
    if not manifest.entrypoint:
        missing.append("entrypoint")
    if not manifest.class_name:
        missing.append("class")
    if missing:
        raise PluginValidationError(
            f"plugin.yaml in '{manifest.directory}' missing required "
            f"field(s): {', '.join(missing)}"
        )


def _load_entrypoint(manifest: PluginManifest) -> type:
    """Import the entrypoint module and return the plugin class."""
    entry = manifest.entrypoint
    plugin_dir = manifest.directory

    if entry.endswith(".py"):
        full_path = plugin_dir / entry
        if not full_path.is_file():
            raise PluginLoadError(
                f"Plugin '{manifest.name}' entrypoint file not found: "
                f"'{full_path}'"
            )
        safe_name = _sanitize_module_name(manifest.name)
        path_digest = hashlib.sha256(str(plugin_dir).encode()).hexdigest()[:8]
        module_name = f"_gryps_plugin_{safe_name}_{path_digest}"
        spec = importlib.util.spec_from_file_location(module_name, str(full_path))
        if spec is None or spec.loader is None:
            raise PluginLoadError(
                f"Could not create module spec for plugin "
                f"'{manifest.name}' at '{full_path}'"
            )
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to execute plugin module '{manifest.name}': {exc}"
            ) from exc
    else:
        try:
            module = importlib.import_module(entry)
        except ImportError as exc:
            raise PluginLoadError(
                f"Failed to import entrypoint '{entry}' "
                f"for plugin '{manifest.name}': {exc}"
            ) from exc

    cls = getattr(module, manifest.class_name, None)
    if cls is None:
        raise PluginLoadError(
            f"Plugin '{manifest.name}' entrypoint module has no "
            f"class '{manifest.class_name}'"
        )
    if not isinstance(cls, type):
        raise PluginLoadError(
            f"Plugin '{manifest.name}' attribute "
            f"'{manifest.class_name}' is not a class"
        )
    return cls


def _sanitize_module_name(name: str) -> str:
    return re.sub(r"\W", "_", name)


# ---------------------------------------------------------------------------
# Minimal YAML parser for plugin.yaml
# ---------------------------------------------------------------------------


def _parse_manifest_yaml(path: Path) -> dict[str, Any]:
    lines = _read_yaml_lines(path)
    result: dict[str, Any] = {}
    _parse_block(lines, 0, -1, result)
    return result


def _read_yaml_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text("utf-8")
    out: list[tuple[int, str]] = []
    for raw_line in text.split("\n"):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        out.append((indent, stripped))
    return out


def _parse_block(
    lines: list[tuple[int, str]],
    start: int,
    parent_indent: int,
    target: dict[str, Any],
) -> int:
    i = start
    while i < len(lines):
        indent, content = lines[i]
        if indent <= parent_indent:
            break

        colon = content.find(":")
        if colon == -1:
            i += 1
            continue

        key = content[:colon].strip()
        rest = content[colon + 1:].strip()

        if rest:
            target[key] = _parse_scalar(rest)
            i += 1
        else:
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                if lines[i + 1][1].startswith("- "):
                    items: list[Any] = []
                    j = i + 1
                    while j < len(lines):
                        li, lc = lines[j]
                        if li <= indent:
                            break
                        if lc.startswith("- "):
                            items.append(_parse_scalar(lc[2:]))
                        j += 1
                    target[key] = items
                    i = j
                else:
                    children: dict[str, Any] = {}
                    i = _parse_block(lines, i + 1, indent, children)
                    target[key] = children
            else:
                target[key] = None
                i += 1

    return i


def _parse_scalar(value: str) -> Any:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]

    if value and value[0] in "|>&*!":
        raise PluginValidationError(
            f"Unsupported YAML construct: value starts with "
            f"'{value[0]}'. Use a quoted string for literal "
            f"values that begin with '{value[0]}'."
        )

    lower = value.lower()
    if lower in _SCALAR_BOOL:
        return _SCALAR_BOOL[lower]
    if lower in ("null", "~"):
        return None

    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass

    return value
