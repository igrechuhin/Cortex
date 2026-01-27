import importlib
from types import SimpleNamespace
from unittest.mock import patch


def test_prompts_module_registers_conditional_prompts_when_needed() -> None:
    # Arrange
    # Force all conditional prompts to be defined during module import.
    fake_status = SimpleNamespace(
        memory_bank_initialized=False,
        structure_configured=False,
        cursor_integration_configured=False,
        tiktoken_cache_available=False,
        migration_needed=True,
    )

    import cortex.tools.prompts as prompts

    # Act
    with patch(
        "cortex.tools.config_status.get_project_config_status",
        return_value=fake_status,
    ):
        prompts = importlib.reload(prompts)

        init_text = prompts.initialize_memory_bank()
        structure_text = prompts.setup_project_structure()
        cursor_text = prompts.setup_cursor_integration()
        tiktoken_text = prompts.populate_tiktoken_cache()
        mig_status_text = prompts.check_migration_status()
        mig_mb_text = prompts.migrate_memory_bank()
        mig_proj_text = prompts.migrate_project_structure()
        synapse_text = prompts.setup_synapse("https://example.com/synapse.git")

    # Restore module for other tests
    _ = importlib.reload(prompts)

    # Assert
    assert "Please initialize a Memory Bank" in init_text
    assert (
        "standardized Cortex" in structure_text
        and "project structure" in structure_text
    )
    assert "Please setup Cursor IDE integration" in cursor_text
    assert "populate the bundled tiktoken cache" in tiktoken_text
    assert "needs migration" in mig_status_text.lower()
    assert "migrate my memory bank" in mig_mb_text.lower()
    assert "migrate my project" in mig_proj_text.lower()
    assert "https://example.com/synapse.git" in synapse_text
