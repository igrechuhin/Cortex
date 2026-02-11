import importlib
import sys
from types import SimpleNamespace
from unittest.mock import patch


def test_prompts_module_registers_conditional_prompts_when_needed() -> None:
    """Setup prompts in cortex.setup.prompts register conditionally."""
    # Test migration scenario (migration_needed=True)
    fake_status_migration = SimpleNamespace(
        memory_bank_initialized=False,
        structure_configured=False,
        cursor_integration_configured=False,
        tiktoken_cache_available=False,
        migration_needed=True,
    )

    with patch(
        "cortex.tools.config_status.get_project_config_status",
        return_value=fake_status_migration,
    ):
        if "cortex.setup.prompts" in sys.modules:
            del sys.modules["cortex.setup.prompts"]
        import cortex.setup.prompts as prompts_migration

        migrate_text = prompts_migration.migrate()
        tiktoken_text_migration = prompts_migration.populate_tiktoken_cache()
        # initialize should NOT be registered when migration is needed
        assert not hasattr(prompts_migration, "initialize")

    # Test initialization scenario (migration_needed=False)
    fake_status_init = SimpleNamespace(
        memory_bank_initialized=False,
        structure_configured=False,
        cursor_integration_configured=False,
        tiktoken_cache_available=False,
        migration_needed=False,
    )

    with patch(
        "cortex.tools.config_status.get_project_config_status",
        return_value=fake_status_init,
    ):
        if "cortex.setup.prompts" in sys.modules:
            del sys.modules["cortex.setup.prompts"]
        import cortex.setup.prompts as prompts_init

        init_text = prompts_init.initialize()
        tiktoken_text_init = prompts_init.populate_tiktoken_cache()
        # migrate should NOT be registered when migration is not needed
        assert not hasattr(prompts_init, "migrate")

    import cortex.setup.prompts_always as prompts_always

    # Test with default parameter
    synapse_text_default = prompts_always.setup_synapse()
    # Test with custom URL
    synapse_text_custom = prompts_always.setup_synapse(
        "https://example.com/synapse.git"
    )

    # Restore module for other tests
    if "cortex.setup.prompts" in sys.modules:
        del sys.modules["cortex.setup.prompts"]
    _ = importlib.import_module("cortex.setup.prompts")

    # Assert
    assert "Please initialize Cortex" in init_text or "initialize Cortex" in init_text
    assert "migrate" in migrate_text.lower()
    assert "populate the bundled tiktoken cache" in tiktoken_text_migration
    assert "populate the bundled tiktoken cache" in tiktoken_text_init
    assert "https://github.com/igrechuhin/Synapse.git" in synapse_text_default
    assert "https://example.com/synapse.git" in synapse_text_custom
