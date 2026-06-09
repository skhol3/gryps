from __future__ import annotations

import re
from pathlib import Path

import pytest

from gryps.core.exceptions import PluginLoadError, PluginValidationError
from gryps.core.registry import (
    PluginManifest,
    PluginRegistry,
    _load_manifest,
    _parse_manifest_yaml,
    _validate_manifest,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "plugins"
DUMMY = FIXTURES / "dummy_plugin"


# ── YAML parser ──────────────────────────────────────────────────────────


class TestYamlParsing:
    def test_parse_valid_manifest(self) -> None:
        data = _parse_manifest_yaml(DUMMY / "plugin.yaml")
        assert data["name"] == "dummy_plugin"
        assert data["version"] == "1.0.0"
        assert data["type"] == "test"
        assert data["entrypoint"] == "plugin.py"
        assert data["class"] == "DummyPlugin"

    def test_parse_comments_ignored(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("# comment\nname: test\n# another\nversion: 1.0\n")
        data = _parse_manifest_yaml(p)
        assert data == {"name": "test", "version": 1.0}

    def test_parse_quoted_strings(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text('name: "hello"\ndesc: \'world\'\n')
        data = _parse_manifest_yaml(p)
        assert data["name"] == "hello"
        assert data["desc"] == "world"

    def test_parse_booleans(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("a: true\nb: false\nc: yes\nd: no\n")
        data = _parse_manifest_yaml(p)
        assert data["a"] is True
        assert data["b"] is False
        assert data["c"] is True
        assert data["d"] is False

    def test_parse_numeric_values(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("i: 42\nf: 3.14\nneg: -1\n")
        data = _parse_manifest_yaml(p)
        assert data["i"] == 42
        assert data["f"] == 3.14
        assert data["neg"] == -1

    def test_parse_null_values(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("a: null\nb: ~\n")
        data = _parse_manifest_yaml(p)
        assert data["a"] is None
        assert data["b"] is None

    def test_parse_empty_value(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("key:\n")
        data = _parse_manifest_yaml(p)
        assert data["key"] is None

    def test_parse_list_values(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("items:\n  - a\n  - b\n  - 42\n")
        data = _parse_manifest_yaml(p)
        assert data["items"] == ["a", "b", 42]

    def test_parse_nested_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text("nested:\n  a: 1\n  b: two\n")
        data = _parse_manifest_yaml(p)
        assert data["nested"] == {"a": 1, "b": "two"}

    def test_parse_missing_file_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            _parse_manifest_yaml(p)

    @pytest.mark.parametrize(
        ("yaml_content", "construct_char"),
        [
            ("key: |\n  extra\n", "|"),
            ("key: >\n  extra\n", ">"),
            ("key: &anchor\n", "&"),
            ("key: *alias\n", "*"),
            ("key: !tag\n", "!"),
        ],
    )
    def test_unsupported_yaml_construct_raises(
        self, tmp_path: Path, yaml_content: str, construct_char: str,
    ) -> None:
        p = tmp_path / "plugin.yaml"
        p.write_text(yaml_content)
        with pytest.raises(PluginValidationError, match=re.escape(construct_char)):
            _parse_manifest_yaml(p)


# ── Manifest loading / validation ────────────────────────────────────────


class TestManifestLoading:
    def test_load_dummy_manifest(self) -> None:
        manifest = _load_manifest(DUMMY / "plugin.yaml")
        assert manifest.name == "dummy_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.entrypoint == "plugin.py"
        assert manifest.class_name == "DummyPlugin"
        assert manifest.type == "test"
        assert manifest.directory == DUMMY
        assert "name" in manifest.raw


class TestManifestValidation:
    def test_valid_passes(self) -> None:
        m = PluginManifest(
            name="test", version="1.0", entrypoint="mod.py", class_name="Cls",
        )
        _validate_manifest(m)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("name", ""),
            ("version", ""),
            ("entrypoint", ""),
            ("class_name", ""),  # error message uses "class" (YAML field)
        ],
    )
    def test_missing_required_field(
        self, field: str, value: str,
    ) -> None:
        kwargs = {
            "name": "test",
            "version": "1.0",
            "entrypoint": "m.py",
            "class_name": "C",
        }
        kwargs[field] = value
        m = PluginManifest(**kwargs)  # type: ignore[arg-type]
        yaml_field = "class" if field == "class_name" else field
        with pytest.raises(PluginValidationError, match=yaml_field):
            _validate_manifest(m)

    def test_multiple_missing(self) -> None:
        m = PluginManifest(
            name="", version="", entrypoint="", class_name="",
        )
        with pytest.raises(PluginValidationError) as exc:
            _validate_manifest(m)
        assert "name" in str(exc.value)
        assert "version" in str(exc.value)
        assert "entrypoint" in str(exc.value)
        assert "class" in str(exc.value)


# ── PluginRegistry — scan ────────────────────────────────────────────────


class TestRegistryScan:
    def test_empty_roots_returns_empty_list(self) -> None:
        reg = PluginRegistry()
        assert reg.scan() == []

    def test_add_root_then_scan(self) -> None:
        reg = PluginRegistry()
        reg.add_root(str(DUMMY))
        manifests = reg.scan()
        assert len(manifests) == 1

    def test_finds_dummy_plugin(self) -> None:
        reg = PluginRegistry(roots=[str(FIXTURES)])
        manifests = reg.scan()
        assert len(manifests) == 1
        m = manifests[0]
        assert m.name == "dummy_plugin"
        assert m.version == "1.0.0"
        assert m.entrypoint == "plugin.py"
        assert m.class_name == "DummyPlugin"

    def test_scan_nonexistent_root_returns_empty(self) -> None:
        reg = PluginRegistry(roots=["/tmp/nonexistent_gryps_xyz"])
        assert reg.scan() == []

    def test_scan_mixed_valid_and_invalid_roots(self) -> None:
        reg = PluginRegistry(roots=[str(FIXTURES), "/tmp/nonexistent"])
        manifests = reg.scan()
        assert len(manifests) == 1

    def test_invalid_yaml_parsed_but_not_validated(self, tmp_path: Path) -> None:
        d = tmp_path / "bad"
        d.mkdir()
        (d / "plugin.yaml").write_text(": : : garbage\n")
        reg = PluginRegistry(roots=[str(d)])
        manifests = reg.scan()
        # scan does NOT validate — returns whatever was parsed
        assert len(manifests) == 1
        assert manifests[0].name == ""


# ── PluginRegistry — discover ────────────────────────────────────────────


class TestRegistryDiscover:
    def test_discover_loads_plugin_class(self) -> None:
        reg = PluginRegistry(roots=[str(FIXTURES)])
        plugins = reg.discover()
        assert "dummy_plugin" in plugins
        info = plugins["dummy_plugin"]
        assert info.loaded_class is not None
        instance = info.loaded_class()
        assert instance.process() == "dummy_processed"

    def test_plugins_property_returns_snapshot(self) -> None:
        reg = PluginRegistry(roots=[str(FIXTURES)])
        reg.discover()
        snap = reg.plugins
        assert "dummy_plugin" in snap
        assert snap is not reg.plugins

    def test_discover_twice_resets(self) -> None:
        reg = PluginRegistry(roots=[str(FIXTURES)])
        p1 = reg.discover()
        p2 = reg.discover()
        assert set(p1) == set(p2)
        assert p1["dummy_plugin"].manifest == p2["dummy_plugin"].manifest

    def test_discover_no_roots_returns_empty(self) -> None:
        reg = PluginRegistry(roots=[])
        assert reg.discover() == {}

    def test_add_root_then_discover(self) -> None:
        reg = PluginRegistry()
        reg.add_root(str(FIXTURES))
        plugins = reg.discover()
        assert "dummy_plugin" in plugins

    def test_invalid_yaml_raises_validation_error(self, tmp_path: Path) -> None:
        d = tmp_path / "bad"
        d.mkdir()
        (d / "plugin.yaml").write_text(": : : garbage\n")
        reg = PluginRegistry(roots=[str(d)])
        manifests = reg.scan()
        assert len(manifests) == 1
        with pytest.raises(PluginValidationError):
            reg.discover()


# ── Duplicate detection ──────────────────────────────────────────────────


class TestDuplicateDetection:
    def test_duplicate_name_raises(self, tmp_path: Path) -> None:
        d1 = tmp_path / "p1"
        d2 = tmp_path / "p2"
        d1.mkdir()
        d2.mkdir()
        for d in (d1, d2):
            (d / "plugin.yaml").write_text(
                "name: dup\nversion: 1.0\nentrypoint: plugin.py\nclass: X\n"
            )
            (d / "plugin.py").write_text("class X: pass\n")
        reg = PluginRegistry(roots=[str(d1), str(d2)])
        with pytest.raises(PluginLoadError, match="Duplicate plugin name"):
            reg.discover()

    def test_non_duplicate_names_ok(self, tmp_path: Path) -> None:
        d1 = tmp_path / "p1"
        d2 = tmp_path / "p2"
        d1.mkdir()
        d2.mkdir()
        for i, d in enumerate([d1, d2]):
            (d / "plugin.yaml").write_text(
                f"name: plugin_{i}\nversion: 1.0\nentrypoint: plugin.py\n"
                f"class: X\n"
            )
            (d / "plugin.py").write_text("class X: pass\n")
        reg = PluginRegistry(roots=[str(d1), str(d2)])
        plugins = reg.discover()
        assert "plugin_0" in plugins
        assert "plugin_1" in plugins

    def test_sanitized_name_collision_avoided(self, tmp_path: Path) -> None:
        d1 = tmp_path / "p1"
        d2 = tmp_path / "p2"
        d1.mkdir()
        d2.mkdir()
        for d, name in ((d1, "my-plugin"), (d2, "my_plugin")):
            (d / "plugin.yaml").write_text(
                f"name: {name}\nversion: 1.0\nentrypoint: plugin.py\nclass: X\n"
            )
            (d / "plugin.py").write_text("class X: pass\n")
        reg = PluginRegistry(roots=[str(d1), str(d2)])
        plugins = reg.discover()
        assert "my-plugin" in plugins
        assert "my_plugin" in plugins

    def test_duplicate_root_does_not_cause_false_duplicate(self, tmp_path: Path) -> None:
        d = tmp_path / "p1"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: my_plugin\nversion: 1.0\nentrypoint: plugin.py\nclass: X\n"
        )
        (d / "plugin.py").write_text("class X: pass\n")
        reg = PluginRegistry()
        reg.add_root(str(d))
        reg.add_root(str(d))
        reg.discover()
        assert "my_plugin" in reg.plugins


# ── Plugin loading errors ────────────────────────────────────────────────


class TestPluginLoadingErrors:
    def test_missing_entrypoint_file(self, tmp_path: Path) -> None:
        d = tmp_path / "broken"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: broken\nversion: 1.0\nentrypoint: nonexistent.py\nclass: X\n"
        )
        reg = PluginRegistry(roots=[str(d)])
        with pytest.raises(PluginLoadError, match="entrypoint file not found"):
            reg.discover()

    def test_missing_class_in_module(self, tmp_path: Path) -> None:
        d = tmp_path / "noclass"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: noclass\nversion: 1.0\nentrypoint: plugin.py\nclass: MissingCls\n"
        )
        (d / "plugin.py").write_text("class SomeOtherClass: pass\n")
        reg = PluginRegistry(roots=[str(d)])
        with pytest.raises(PluginLoadError, match="has no class"):
            reg.discover()

    def test_class_not_a_type(self, tmp_path: Path) -> None:
        d = tmp_path / "notype"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: notype\nversion: 1.0\nentrypoint: plugin.py\nclass: some_var\n"
        )
        (d / "plugin.py").write_text("some_var = 42\n")
        reg = PluginRegistry(roots=[str(d)])
        with pytest.raises(PluginLoadError, match="is not a class"):
            reg.discover()

    def test_spec_is_none_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        d = tmp_path / "nospec"
        d.mkdir()
        (d / "plugin.yaml").write_text(
            "name: nospec\nversion: 1.0\nentrypoint: plugin.py\nclass: X\n"
        )
        (d / "plugin.py").write_text("class X: pass\n")
        monkeypatch.setattr(
            "importlib.util.spec_from_file_location",
            lambda *_: None,
        )
        reg = PluginRegistry(roots=[str(d)])
        with pytest.raises(PluginLoadError, match="Could not create module spec"):
            reg.discover()
