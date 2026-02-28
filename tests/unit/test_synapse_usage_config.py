"""Unit tests for Synapse usage config (usage_writable, static snapshot)."""

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.synapse_usage_config import (
    get_usage_storage_root,
    is_usage_writable,
    load_synapse_usage_config,
)


def _make_project_root(tmp_path: Path) -> Path:
    """Create project root with .cortex directory."""
    root = tmp_path / "project"
    (root / ".cortex").mkdir(parents=True)
    return root


class TestLoadSynapseUsageConfig:
    """Tests for load_synapse_usage_config."""

    def test_returns_false_when_config_missing(self, tmp_path: Path) -> None:
        """When .cortex/synapse/config.json is missing, returns usage_writable False."""
        root = _make_project_root(tmp_path)
        config = load_synapse_usage_config(root)
        assert config.get("usage_writable") is False

    def test_returns_false_when_synapse_missing(self, tmp_path: Path) -> None:
        """When .cortex/synapse directory is missing, returns usage_writable False."""
        root = _make_project_root(tmp_path)
        config = load_synapse_usage_config(root)
        assert config.get("usage_writable") is False

    def test_returns_false_when_usage_writable_false(self, tmp_path: Path) -> None:
        """When config has usage_writable: false, returns False."""
        root = _make_project_root(tmp_path)
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text(
            '{"usage_writable": false}', encoding="utf-8"
        )
        config = load_synapse_usage_config(root)
        assert config.get("usage_writable") is False

    def test_returns_true_when_usage_writable_true(self, tmp_path: Path) -> None:
        """When config has usage_writable: true, returns True."""
        root = _make_project_root(tmp_path)
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text(
            '{"usage_writable": true}', encoding="utf-8"
        )
        config = load_synapse_usage_config(root)
        assert config.get("usage_writable") is True

    def test_returns_false_on_invalid_json(self, tmp_path: Path) -> None:
        """When config is invalid JSON, returns usage_writable False."""
        root = _make_project_root(tmp_path)
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text("not json", encoding="utf-8")
        config = load_synapse_usage_config(root)
        assert config.get("usage_writable") is False

    def test_returns_false_when_key_absent(self, tmp_path: Path) -> None:
        """When config exists but usage_writable key absent, returns False."""
        root = _make_project_root(tmp_path)
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text('{"other": 1}', encoding="utf-8")
        config = load_synapse_usage_config(root)
        assert config.get("usage_writable") is False


class TestIsUsageWritable:
    """Tests for is_usage_writable helper."""

    def test_false_when_config_missing(self, tmp_path: Path) -> None:
        """Returns False when config missing."""
        root = _make_project_root(tmp_path)
        assert is_usage_writable(root) is False

    def test_true_when_usage_writable_true(self, tmp_path: Path) -> None:
        """Returns True when usage_writable: true in config."""
        root = _make_project_root(tmp_path)
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text(
            '{"usage_writable": true}', encoding="utf-8"
        )
        assert is_usage_writable(root) is True


class TestGetUsageStorageRoot:
    """Tests for get_usage_storage_root."""

    def test_returns_project_cache_when_not_writable(self, tmp_path: Path) -> None:
        """When usage_writable false, returns project .cortex/.cache."""
        root = _make_project_root(tmp_path)
        cortex_dir = root / ".cortex"
        result = get_usage_storage_root(root)
        assert result == cortex_dir / ".cache"

    def test_returns_synapse_cache_when_writable(self, tmp_path: Path) -> None:
        """When usage_writable true and Synapse exists, returns synapse/.cache."""
        root = _make_project_root(tmp_path)
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text(
            '{"usage_writable": true}', encoding="utf-8"
        )
        result = get_usage_storage_root(root)
        assert result == synapse_dir / ".cache"
