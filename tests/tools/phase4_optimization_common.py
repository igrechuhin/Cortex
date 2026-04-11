"""
Comprehensive tests for Phase 4: Token Optimization Tools

This test suite provides comprehensive coverage for:
- load_context()
- load_progressive_context()
- summarize_content()
- get_relevance_scores()
- All helper functions and error paths
"""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.types import ManagersDict
from cortex.tools.optimization import (
    get_relevance_scores,
    load_context,
    summarize_content,
)
from cortex.tools.optimization.handlers import (
    get_relevance_scores_resource,
    invalidate_context_resource_cache,
    summarize_content_resource,
)
from cortex.tools.optimization.handlers import (
    load_context_impl as _load_context_impl,
)
from cortex.tools.optimization.handlers_validation import is_non_trivial_task
from cortex.tools.session.models import SESSION_SCOPE_PROMPT
from tests.helpers.managers import make_test_managers
from tests.helpers.phase4_optimization_managers import build_phase4_mock_managers
from tests.helpers.phase4_optimization_test_helpers import (
    run_concise_load_context_with_payload,
    run_full_context_score_summarize_workflow,
    run_load_context_impl_with_zero_files_handling_mock,
    run_load_context_with_log_client_patched,
    run_summarize_with_config_overrides,
)

# ============================================================================
# Helper Functions
# ============================================================================


def _get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
    """Helper function to get manager by field name."""
    return getattr(mgrs, key)


def write_test_operations_log(mock_project_root: Path) -> None:
    """Create a small operations log fixture under .cortex/memory-bank."""
    memory_bank_dir = mock_project_root / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    log_content = "\n".join(
        [
            "# Cortex Operations Log",
            "",
            "## [2026-04-07T10:00] plan | Created plan: One",
            "",
            "A",
            "",
            "## [2026-04-07T10:05] fix | Applied autofix",
            "",
            "B",
            "",
        ]
    )
    _ = (memory_bank_dir / "log.md").write_text(log_content, encoding="utf-8")


def write_test_artifact_pages(mock_project_root: Path) -> None:
    """Create sample filed artifact pages under memory-bank/reviews."""
    memory_bank_dir = mock_project_root / ".cortex" / "memory-bank"
    reviews = memory_bank_dir / "reviews"
    reviews.mkdir(parents=True)
    _ = (reviews / "review-auth-2026-04-07.md").write_text(
        "# Auth Review\n\nFirst finding text.", encoding="utf-8"
    )


def write_scoped_plan_fixtures(mock_project_root: Path) -> None:
    plans_dir = mock_project_root / ".cortex" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    _ = (plans_dir / "dep-one.md").write_text(
        "---\nstatus: DONE\ndepends_on: []\n---\n## Goal\nDependency plan.\n",
        encoding="utf-8",
    )
    _ = (plans_dir / "scoped-plan.md").write_text(
        (
            '---\nstatus: PENDING\ndepends_on: ["dep-one"]\n---\n'
            "## Goal\nImplement python schema tests.\n"
        ),
        encoding="utf-8",
    )
    _ = (plans_dir / "scoped-other.md").write_text(
        "---\nstatus: PENDING\ndepends_on: []\n---\n## Goal\nImplement mcp tools.\n",
        encoding="utf-8",
    )


def _build_scoped_rules_payload() -> str:
    return json.dumps(
        {
            "status": "success",
            "rules": [
                {"content": "## Universal\n<!-- task_types: ALL -->\nAlways keep."},
                {
                    "content": "## Core Logic\n<!-- task_types: CORE_LOGIC -->\nUse typing."
                },
                {"content": "## MCP\n<!-- task_types: MCP_TOOL -->\nRegister tools."},
            ],
        }
    )


async def load_scoped_context_result(
    mock_project_root: Path,
    mock_managers: dict[str, Any],
) -> dict[str, Any]:
    with (
        patch(
            "cortex.core.session_config.read_session_config",
            return_value={
                "task_description": "Scoped context test",
                "scope": "plan:scoped-plan",
            },
        ),
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch("cortex.tools.optimization.get_managers", return_value=mock_managers),
        patch(
            "cortex.tools.context.load_operations.get_manager",
            side_effect=_get_manager_helper,
        ),
        patch(
            "cortex.tools.optimization.handlers.get_relevant_rules",
            new_callable=AsyncMock,
            return_value=_build_scoped_rules_payload(),
        ),
    ):
        return cast(dict[str, Any], json.loads(await load_context()))


async def load_scoped_context_with_cfg(
    mock_project_root: Path,
    mock_managers: dict[str, Any],
    session_cfg: dict[str, object],
) -> dict[str, Any]:
    with (
        patch(
            "cortex.core.session_config.read_session_config", return_value=session_cfg
        ),
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch("cortex.tools.optimization.get_managers", return_value=mock_managers),
        patch(
            "cortex.tools.context.load_operations.get_manager",
            side_effect=_get_manager_helper,
        ),
        patch(
            "cortex.tools.optimization.handlers.get_relevant_rules",
            new_callable=AsyncMock,
            return_value=_build_scoped_rules_payload(),
        ),
    ):
        return cast(dict[str, Any], json.loads(await load_context()))


def scoped_scope(result: dict[str, Any]) -> object:
    scoped = cast(dict[str, object], result.get("scoped_context"))
    return scoped.get("scope")


def _build_scope_switchers() -> tuple[object, object]:
    state: dict[str, object] = {"scope": "plan:one", "cache_calls": 0}

    def resolve_scope() -> str:
        calls = cast(int, state["cache_calls"]) + 1
        state["cache_calls"] = calls
        if calls > 1:
            state["scope"] = "plan:two"
        return cast(str, state["scope"])

    def read_cfg() -> dict[str, str]:
        return {
            "task_description": "Scoped cache test",
            "scope": cast(str, state["scope"]),
        }

    return resolve_scope, read_cfg


async def load_context_scope_cache_results(
    mock_project_root: Path,
    payload_one: str,
    payload_two: str,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    resolve_scope, read_cfg = _build_scope_switchers()
    with (
        patch("cortex.core.session_config.read_session_config", side_effect=read_cfg),
        patch(
            "cortex.tools.optimization.handlers._resolve_context_cache_scope",
            side_effect=resolve_scope,
        ),
        patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=mock_project_root,
        ),
        patch(
            "cortex.tools.optimization.handlers.load_context_impl",
            new_callable=AsyncMock,
            side_effect=[payload_one, payload_two],
        ) as mock_load_context_impl,
        patch(
            "cortex.tools.optimization.handlers._build_context_resource_payload_async",
            new_callable=AsyncMock,
            side_effect=[payload_one, payload_two],
        ),
    ):
        first_result = cast(dict[str, Any], json.loads(await load_context()))
        second_result = cast(dict[str, Any], json.loads(await load_context()))
    return first_result, second_result, mock_load_context_impl.await_count


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_optimization_result() -> MagicMock:
    """Create mock optimization result."""
    return MagicMock(
        selected_files=["file1.md", "file2.md"],
        selected_sections={"file1.md": ["Section 1"]},
        total_tokens=5000,
        utilization=0.5,
        excluded_files=["file3.md"],
        metadata={"relevance_scores": {"file1.md": 0.9, "file2.md": 0.8}},
    )


@pytest.fixture
def mock_loaded_content() -> list[Any]:
    """Create mock loaded content items."""

    class MockLoadedContent:
        def __init__(
            self,
            file_name: str,
            tokens: int,
            cumulative: int,
            priority: int,
            relevance: float,
        ) -> None:
            self.file_name = file_name
            self.tokens = tokens
            self.cumulative_tokens = cumulative
            self.priority = priority
            self.relevance_score = relevance
            self.more_available = False

    return [
        MockLoadedContent("file1.md", 1000, 1000, 1, 0.9),
        MockLoadedContent("file2.md", 2000, 3000, 2, 0.8),
    ]


@pytest.fixture
def mock_managers(
    mock_optimization_result: MagicMock, mock_loaded_content: list[Any]
) -> ManagersDict:
    """Create typed mock managers container (see tests/FIXTURE_REQUIREMENTS.md)."""
    return build_phase4_mock_managers(mock_optimization_result, mock_loaded_content)


__all__ = [
    "Any",
    "AsyncMock",
    "MagicMock",
    "ManagersDict",
    "Path",
    "SESSION_SCOPE_PROMPT",
    "_get_manager_helper",
    "_load_context_impl",
    "build_phase4_mock_managers",
    "cast",
    "get_relevance_scores",
    "get_relevance_scores_resource",
    "invalidate_context_resource_cache",
    "is_non_trivial_task",
    "json",
    "load_context",
    "load_context_scope_cache_results",
    "load_scoped_context_result",
    "load_scoped_context_with_cfg",
    "make_test_managers",
    "mock_loaded_content",
    "mock_managers",
    "mock_optimization_result",
    "mock_project_root",
    "patch",
    "pytest",
    "run_concise_load_context_with_payload",
    "run_full_context_score_summarize_workflow",
    "run_load_context_impl_with_zero_files_handling_mock",
    "run_load_context_with_log_client_patched",
    "run_summarize_with_config_overrides",
    "scoped_scope",
    "summarize_content",
    "summarize_content_resource",
    "write_scoped_plan_fixtures",
    "write_test_artifact_pages",
    "write_test_operations_log",
]
