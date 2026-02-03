"""
Integration tests for conditional prompt registration.

Setup prompts live in cortex.setup.prompts and register conditionally
based on project configuration status.
"""

import sys
from pathlib import Path
from unittest.mock import patch


def _clear_setup_prompts_cache() -> None:
    """Remove cortex.setup.prompts from sys.modules so it is re-imported."""
    if "cortex.setup.prompts" in sys.modules:
        del sys.modules["cortex.setup.prompts"]


class TestConditionalPromptRegistration:
    """Test conditional registration of setup prompts based on config status."""

    def test_prompts_not_registered_when_configured(self, tmp_path: Path):
        """Test that setup prompts are not registered when project is configured."""
        # Arrange - Create fully configured project
        cortex_dir = tmp_path / ".cortex"
        cortex_dir.mkdir()
        (cortex_dir / "memory-bank").mkdir()
        (cortex_dir / "rules").mkdir()
        (cortex_dir / "plans").mkdir()
        (cortex_dir / "config").mkdir()

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

        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        (cortex_dir / "synapse").mkdir()
        (cursor_dir / "memory-bank").symlink_to(cortex_dir / "memory-bank")
        (cursor_dir / "synapse").symlink_to(cortex_dir / "synapse")
        (cursor_dir / "plans").symlink_to(cortex_dir / "plans")

        # Act - Import setup prompts with mocked project root
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            # Assert - Setup prompts should not be registered
            assert not hasattr(prompts_module, "initialize_memory_bank")
            assert not hasattr(prompts_module, "setup_project_structure")
            assert not hasattr(prompts_module, "setup_cursor_integration")
            assert not hasattr(prompts_module, "check_migration_status")
            assert not hasattr(prompts_module, "migrate_memory_bank")
            assert not hasattr(prompts_module, "migrate_project_structure")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_prompts_registered_when_not_configured(self, tmp_path: Path):
        """Test that setup prompts are registered when project is not configured."""
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            assert hasattr(prompts_module, "initialize_memory_bank")
            assert hasattr(prompts_module, "setup_project_structure")
            assert hasattr(prompts_module, "setup_cursor_integration")
            assert not hasattr(prompts_module, "check_migration_status")
            assert not hasattr(prompts_module, "migrate_memory_bank")
            assert not hasattr(prompts_module, "migrate_project_structure")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_migration_prompts_registered_when_migration_needed(self, tmp_path: Path):
        """Test that migration prompts are registered when migration is needed."""
        legacy_path = tmp_path / ".cursor" / "memory-bank"
        legacy_path.mkdir(parents=True)
        _ = (legacy_path / "old.md").write_text("# Test")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            assert hasattr(prompts_module, "check_migration_status")
            assert hasattr(prompts_module, "migrate_memory_bank")
            assert hasattr(prompts_module, "migrate_project_structure")
            assert hasattr(prompts_module, "initialize_memory_bank")
            assert hasattr(prompts_module, "setup_project_structure")
            assert hasattr(prompts_module, "setup_cursor_integration")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_partial_configuration_registers_partial_prompts(self, tmp_path: Path):
        """Test that partial configuration registers only needed prompts."""
        cortex_dir = tmp_path / ".cortex"
        cortex_dir.mkdir()
        (cortex_dir / "memory-bank").mkdir()

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
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            _clear_setup_prompts_cache()
            import cortex.setup.prompts as prompts_module

            assert not hasattr(prompts_module, "initialize_memory_bank")
            assert hasattr(prompts_module, "setup_project_structure")
            assert hasattr(prompts_module, "setup_cursor_integration")
            import cortex.setup.prompts_always as always_module

            assert hasattr(always_module, "setup_synapse")

    def test_setup_synapse_always_available(self, tmp_path: Path):
        """Test that setup_synapse is always available from prompts_always."""
        import cortex.setup.prompts_always as always_module

        assert hasattr(always_module, "setup_synapse")
        text = always_module.setup_synapse("https://example.com/repo.git")
        assert "synapse" in text.lower()
        assert "https://example.com/repo.git" in text
