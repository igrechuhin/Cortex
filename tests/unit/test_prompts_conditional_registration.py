import importlib
import sys
from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from typing import cast
from unittest.mock import patch


def _reload_prompts_module() -> ModuleType:
    """Force a fresh import of cortex.setup.prompts so decorators re-evaluate."""
    if "cortex.setup.prompts" in sys.modules:
        del sys.modules["cortex.setup.prompts"]
    return importlib.import_module("cortex.setup.prompts")


def _text_fn(module: ModuleType, name: str) -> Callable[[], str]:
    """Cast a dynamically-registered zero-arg prompt function to a typed callable."""
    return cast(Callable[[], str], getattr(module, name))


def _exercise_migration_scenario() -> tuple[str, str]:
    """Reload prompts with migration_needed=True; return (migrate, tiktoken) text."""
    fake_status_migration = SimpleNamespace(
        memory_bank_initialized=False,
        structure_configured=False,
        tiktoken_cache_available=False,
        migration_needed=True,
    )
    with patch(
        "cortex.tools.config.get_project_config_status",
        return_value=fake_status_migration,
    ):
        prompts_migration = _reload_prompts_module()
        with patch(
            "cortex.setup.prompts.apply_project_post_edit_hook"
        ) as migration_hook_patch:
            migrate_text = _text_fn(prompts_migration, "migrate")()
            migration_hook_patch.assert_called_once()
        tiktoken_text = _text_fn(prompts_migration, "populate_tiktoken_cache")()
        # initialize should NOT be registered when migration is needed
        assert not hasattr(prompts_migration, "initialize")
    return migrate_text, tiktoken_text


def _exercise_initialization_scenario() -> tuple[str, str]:
    """Reload prompts with migration_needed=False; return (init, tiktoken) text."""
    fake_status_init = SimpleNamespace(
        memory_bank_initialized=False,
        structure_configured=False,
        tiktoken_cache_available=False,
        migration_needed=False,
    )
    with patch(
        "cortex.tools.config.get_project_config_status",
        return_value=fake_status_init,
    ):
        prompts_init = _reload_prompts_module()
        with patch(
            "cortex.setup.prompts.apply_project_post_edit_hook"
        ) as init_hook_patch:
            init_text = _text_fn(prompts_init, "initialize")()
            init_hook_patch.assert_called_once()
        tiktoken_text = _text_fn(prompts_init, "populate_tiktoken_cache")()
        # migrate should NOT be registered when migration is not needed
        assert not hasattr(prompts_init, "migrate")
    return init_text, tiktoken_text


def test_prompts_module_registers_conditional_prompts_when_needed() -> None:
    """Setup prompts in cortex.setup.prompts register conditionally."""
    migrate_text, tiktoken_text_migration = _exercise_migration_scenario()
    init_text, tiktoken_text_init = _exercise_initialization_scenario()

    import cortex.setup.prompts_always as prompts_always

    synapse_text_default = prompts_always.setup_synapse()
    synapse_text_custom = prompts_always.setup_synapse(
        "https://example.com/synapse.git"
    )

    # Restore module for other tests
    _ = _reload_prompts_module()

    # Assert
    assert "Please initialize Cortex" in init_text or "initialize Cortex" in init_text
    assert "migrate" in migrate_text.lower()
    assert "populate the bundled tiktoken cache" in tiktoken_text_migration
    assert "populate the bundled tiktoken cache" in tiktoken_text_init
    assert "https://github.com/igrechuhin/Synapse.git" in synapse_text_default
    assert "https://example.com/synapse.git" in synapse_text_custom
