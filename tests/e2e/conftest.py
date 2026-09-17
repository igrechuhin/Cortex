"""Isolated real managers for public workflow tests, including transport telemetry."""

import importlib
import sys
from collections.abc import AsyncIterator
from contextvars import ContextVar
from pathlib import Path

import pytest
from tiktoken.registry import get_encoding

from cortex.core.manager_registry import ManagerRegistry
from cortex.core.session_config import SessionConfig
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.rules_manager import RulesManager
from cortex.tools.optimization.handlers import invalidate_context_resource_cache
from cortex.tools.synapse.rules_operations import invalidate_rules_resource_cache
from tests.e2e.public_workflow_helpers import write_memory_bank, write_quality_project
from tests.integration import test_hybrid_rules_delivery as rule_fixtures

hybrid_rules_manager = rule_fixtures.hybrid_rules_manager


def _isolate_public_context(
    root: Path, managers: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch only request context boundaries, never tool behavior or managers."""
    monkeypatch.setenv("CORTEX_SESSION_ID", "publicsmoke01")
    monkeypatch.setenv("CORTEX_PYTEST_PARALLEL", "0")
    monkeypatch.setattr(
        "cortex.core.usage_context._current_managers",
        ContextVar("public_managers", default=managers),
    )
    monkeypatch.setattr(
        "cortex.core.usage_context._current_project_root",
        ContextVar("public_project_root", default=root),
    )
    # This fixture supplies an initialized workspace, not wiki bootstrap coverage.
    monkeypatch.setattr(
        "cortex.core.project_root_resolver.wiki_bootstrapped_roots",
        {root.resolve().as_posix()},
    )
    monkeypatch.setattr(
        "cortex.core.session_config.read_session_config",
        lambda: SessionConfig(
            task_description="python", token_budget=12000, check_type="schema"
        ),
    )


@pytest.fixture
async def public_project(
    tmp_path: Path, hybrid_rules_manager: RulesManager, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Path]:
    """Reuse the real shared-rule fixture; keep manager caches and logs local."""
    _ = importlib.import_module("cortex.tools")
    _ = write_memory_bank(tmp_path)
    registry = ManagerRegistry()
    monkeypatch.setattr(
        "cortex.core.manager_registry.get_process_registry", lambda: registry
    )
    monkeypatch.setattr("tiktoken.get_encoding", get_encoding)
    managers = await registry.get_managers(tmp_path)
    managers.tokens.encoding_impl = get_encoding("cl100k_base")
    monkeypatch.setattr(
        "cortex.tools.optimization.handlers.context_token_counter",
        lambda: managers.tokens,
    )
    config = OptimizationConfig(tmp_path)
    _ = config.set("rules.enabled", True)
    _ = config.set("rules.rules_folder", hybrid_rules_manager.rules_folder)
    _ = config.set("rules.min_relevance_score", 0.0)
    managers.optimization_config = config
    managers.rules_manager = hybrid_rules_manager
    _isolate_public_context(tmp_path, managers.model_dump(), monkeypatch)
    invalidate_rules_resource_cache()
    invalidate_context_resource_cache()
    try:
        yield tmp_path
    finally:
        invalidate_rules_resource_cache()
        invalidate_context_resource_cache()
        registry.clear_cache()


@pytest.fixture
def quality_project(public_project: Path) -> Path:
    environment = Path(sys.executable).parent.parent
    write_quality_project(public_project, environment)
    return public_project
