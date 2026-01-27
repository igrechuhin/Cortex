"""
Integration tests for conditional prompt registration.

These tests verify that prompts are conditionally registered based on
project configuration status.
"""

import sys
from pathlib import Path
from unittest.mock import patch


class TestConditionalPromptRegistration:
    """Test conditional registration of prompts based on config status."""

    def test_prompts_not_registered_when_configured(self, tmp_path: Path):
        """Test that setup prompts are not registered when project is configured."""
        # Arrange - Create fully configured project
        cortex_dir = tmp_path / ".cortex"
        cortex_dir.mkdir()
        (cortex_dir / "memory-bank").mkdir()
        (cortex_dir / "rules").mkdir()
        (cortex_dir / "plans").mkdir()
        (cortex_dir / "config").mkdir()

        # Create core memory bank files
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

        # Create .cursor/ with symlinks
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        (cortex_dir / "synapse").mkdir()
        (cursor_dir / "memory-bank").symlink_to(cortex_dir / "memory-bank")
        (cursor_dir / "synapse").symlink_to(cortex_dir / "synapse")
        (cursor_dir / "plans").symlink_to(cortex_dir / "plans")

        # Act - Import prompts module with mocked project root
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Remove module from cache if already imported
            if "cortex.tools.prompts" in sys.modules:
                del sys.modules["cortex.tools.prompts"]

            import cortex.tools.prompts as prompts_module

            # Assert - Setup prompts should not be registered
            assert not hasattr(prompts_module, "initialize_memory_bank")
            assert not hasattr(prompts_module, "setup_project_structure")
            assert not hasattr(prompts_module, "setup_cursor_integration")

            # Migration prompts should not be registered
            assert not hasattr(prompts_module, "check_migration_status")
            assert not hasattr(prompts_module, "migrate_memory_bank")
            assert not hasattr(prompts_module, "migrate_project_structure")

            # setup_synapse should always be available
            assert hasattr(prompts_module, "setup_synapse")

    def test_prompts_registered_when_not_configured(self, tmp_path: Path):
        """Test that setup prompts are registered when project is not configured."""
        # Arrange - Empty project (nothing configured)

        # Act - Import prompts module with mocked project root
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Remove module from cache if already imported
            if "cortex.tools.prompts" in sys.modules:
                del sys.modules["cortex.tools.prompts"]

            import cortex.tools.prompts as prompts_module

            # Assert - Setup prompts should be registered
            assert hasattr(prompts_module, "initialize_memory_bank")
            assert hasattr(prompts_module, "setup_project_structure")
            assert hasattr(prompts_module, "setup_cursor_integration")

            # Migration prompts should not be registered (no legacy format)
            assert not hasattr(prompts_module, "check_migration_status")
            assert not hasattr(prompts_module, "migrate_memory_bank")
            assert not hasattr(prompts_module, "migrate_project_structure")

            # setup_synapse should always be available
            assert hasattr(prompts_module, "setup_synapse")

    def test_migration_prompts_registered_when_migration_needed(self, tmp_path: Path):
        """Test that migration prompts are registered when migration is needed."""
        # Arrange - Create legacy format
        legacy_path = tmp_path / ".cursor" / "memory-bank"
        legacy_path.mkdir(parents=True)
        _ = (legacy_path / "old.md").write_text("# Test")

        # Act - Import prompts module with mocked project root
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Remove module from cache if already imported
            if "cortex.tools.prompts" in sys.modules:
                del sys.modules["cortex.tools.prompts"]

            import cortex.tools.prompts as prompts_module

            # Assert - Migration prompts should be registered
            assert hasattr(prompts_module, "check_migration_status")
            assert hasattr(prompts_module, "migrate_memory_bank")
            assert hasattr(prompts_module, "migrate_project_structure")

            # Setup prompts should also be registered (project not fully configured)
            assert hasattr(prompts_module, "initialize_memory_bank")
            assert hasattr(prompts_module, "setup_project_structure")
            assert hasattr(prompts_module, "setup_cursor_integration")

            # setup_synapse should always be available
            assert hasattr(prompts_module, "setup_synapse")

    def test_partial_configuration_registers_partial_prompts(self, tmp_path: Path):
        """Test that partial configuration registers only needed prompts."""
        # Arrange - Create memory bank but not structure
        cortex_dir = tmp_path / ".cortex"
        cortex_dir.mkdir()
        (cortex_dir / "memory-bank").mkdir()

        # Create core memory bank files
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

        # Missing rules, plans, config directories
        # Missing .cursor/ symlinks

        # Act - Import prompts module with mocked project root
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            # Remove module from cache if already imported
            if "cortex.tools.prompts" in sys.modules:
                del sys.modules["cortex.tools.prompts"]

            import cortex.tools.prompts as prompts_module

            # Assert - initialize_memory_bank should NOT be registered
            # (memory bank exists)
            assert not hasattr(prompts_module, "initialize_memory_bank")

            # setup_project_structure should be registered (structure incomplete)
            assert hasattr(prompts_module, "setup_project_structure")

            # setup_cursor_integration should be registered (cursor integration missing)
            assert hasattr(prompts_module, "setup_cursor_integration")

            # setup_synapse should always be available
            assert hasattr(prompts_module, "setup_synapse")

    def test_setup_synapse_always_available(self, tmp_path: Path):
        """Test that setup_synapse is always available regardless of configuration."""
        # Arrange - Test with both configured and unconfigured states

        # Test 1: Unconfigured project
        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            if "cortex.tools.prompts" in sys.modules:
                del sys.modules["cortex.tools.prompts"]

            import cortex.tools.prompts as prompts_module

            assert hasattr(prompts_module, "setup_synapse")

        # Test 2: Configured project
        cortex_dir = tmp_path / ".cortex"
        cortex_dir.mkdir()
        (cortex_dir / "memory-bank").mkdir()
        (cortex_dir / "rules").mkdir()
        (cortex_dir / "plans").mkdir()
        (cortex_dir / "config").mkdir()

        memory_bank_dir = cortex_dir / "memory-bank"
        for core_file in [
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ]:
            _ = (memory_bank_dir / core_file).write_text("# Test")

        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        (cortex_dir / "synapse").mkdir()
        (cursor_dir / "memory-bank").symlink_to(cortex_dir / "memory-bank")
        (cursor_dir / "synapse").symlink_to(cortex_dir / "synapse")
        (cursor_dir / "plans").symlink_to(cortex_dir / "plans")

        with patch(
            "cortex.tools.config_status.get_project_root", return_value=tmp_path
        ):
            if "cortex.tools.prompts" in sys.modules:
                del sys.modules["cortex.tools.prompts"]

            import cortex.tools.prompts as prompts_module

            assert hasattr(prompts_module, "setup_synapse")
