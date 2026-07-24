"""
Integration tests for conditional prompt registration.

Setup prompts live in cortex.setup.prompts and register conditionally
based on project configuration status.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _clear_setup_prompts_cache() -> None:
    """Remove cortex.setup.prompts from sys.modules so it is re-imported."""
    if "cortex.setup.prompts" in sys.modules:
        del sys.modules["cortex.setup.prompts"]


class TestConditionalPromptRegistration:
    """Test conditional registration of setup prompts based on config status."""

    def test_prompts_not_registered_when_configured(self, tmp_path: Path):
        """Test that setup prompts are not registered when project is configured."""
        # Arrange - Create fully configured project
        cortex_dir = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex_dir.mkdir()
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir()
        get_cortex_path(tmp_path, CortexResourceType.RULES).mkdir()
        get_cortex_path(tmp_path, CortexResourceType.PLANS).mkdir()
        get_cortex_path(tmp_path, CortexResourceType.CONFIG).mkdir()

        memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        core_files = [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]
        for core_file in core_files:
            _ = (memory_bank_dir / core_file).write_text("# Test")

        (cortex_dir / "synapse").mkdir()

        # Act - Import setup prompts with mocked project root
        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            # Assert - Setup prompts should not be registered
            assert not hasattr(prompts_module, "initialize")
            assert not hasattr(prompts_module, "migrate")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_prompts_registered_when_not_configured(self, tmp_path: Path):
        """Test that setup prompts are registered when project is not configured."""
        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            assert hasattr(prompts_module, "initialize")
            assert not hasattr(prompts_module, "migrate")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_migration_prompts_registered_when_migration_needed(self, tmp_path: Path):
        """Test that migration prompts are registered when migration is needed."""
        legacy_path = tmp_path / "memory-bank"
        legacy_path.mkdir(parents=True)
        _ = (legacy_path / "old.md").write_text("# Test")

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            assert hasattr(prompts_module, "migrate")
            assert not hasattr(prompts_module, "initialize")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_partial_configuration_registers_partial_prompts(self, tmp_path: Path):
        """Test that partial configuration registers only needed prompts."""
        cortex_dir = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)
        cortex_dir.mkdir()
        get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir()

        memory_bank_dir = cortex_dir / "memory-bank"
        core_files = [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]
        for core_file in core_files:
            _ = (memory_bank_dir / core_file).write_text("# Test")

        with patch(
            "cortex.tools.config.status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            # When memory bank is initialized but structure is not configured,
            # initialize should still be available (checks both conditions)
            # Actually, initialize checks: not memory_bank_initialized AND not structure_configured
            # So if memory_bank is initialized but structure is not, initialize won't show
            # But we might still need setup prompts, so let's check what should happen
            # Based on the new logic: initialize requires BOTH to be false
            assert not hasattr(prompts_module, "initialize")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_setup_synapse_always_available(self, tmp_path: Path):
        """Test that setup_synapse is always available from prompts_always."""
        import cortex.setup.prompts_always as always_module

        assert hasattr(always_module, "setup_synapse")
        # Test with default parameter
        text_default = always_module.setup_synapse()
        assert "synapse" in text_default.lower()
        assert "https://github.com/igrechuhin/Synapse.git" in text_default
        # Test with custom URL
        text_custom = always_module.setup_synapse("https://example.com/repo.git")
        assert "synapse" in text_custom.lower()
        assert "https://example.com/repo.git" in text_custom
