"""Phase 9.5: Tests for Phase 6 shared rules / Synapse tools.

Tests sync_synapse, update_synapse, get_synapse_rules and related edge cases.
Complements tests/tools/test_synapse_tools.py with Phase 9.5 coverage targets.
"""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import OperationStatus
from cortex.managers.types import ManagersDict
from cortex.rules.models import SynapseSyncResult, SyncChanges
from cortex.tools.synapse_tools import (
    get_synapse_rules,
    sync_synapse,
    update_synapse,
    update_synapse_rule,
)
from tests.helpers.managers import make_test_managers

# ============================================================================
# Helper
# ============================================================================


async def _get_manager_helper(
    mgrs: ManagersDict | dict[str, object], key: str, _: object
) -> object:
    """Resolve manager from container for patched get_manager."""
    if isinstance(mgrs, dict):
        manager = mgrs.get(key)
    else:
        manager = getattr(mgrs, key)
    from cortex.managers.lazy_manager import LazyManager

    if isinstance(manager, LazyManager):
        return cast(object, await manager.get())
    return manager


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path) -> Path:
    """Create mock project root."""
    return tmp_path


@pytest.fixture
def mock_synapse_manager() -> MagicMock:
    """Create mock SynapseManager with sync/update stubs."""
    manager = MagicMock()
    manager.sync_synapse = AsyncMock(
        return_value=SynapseSyncResult(
            status=OperationStatus.SUCCESS,
            pulled=True,
            pushed=False,
            changes=SyncChanges(
                added=[], modified=["rules/python-style.md"], deleted=[]
            ),
            reindex_triggered=True,
            last_sync="2026-01-04T10:30:00Z",
        )
    )
    manager.update_synapse_rule = AsyncMock(
        return_value={"status": "success", "commit_sha": "abc123"}
    )
    manager.update_synapse_prompt = AsyncMock(
        return_value={"status": "success", "commit_sha": "def456"}
    )
    return manager


@pytest.fixture
def mock_rules_manager() -> MagicMock:
    """Create mock RulesManager."""
    manager = MagicMock()
    manager.index_rules = AsyncMock(return_value={"indexed": 5})
    return manager


@pytest.fixture
def mock_managers_with_synapse(
    mock_synapse_manager: MagicMock, mock_rules_manager: MagicMock
) -> ManagersDict:
    """Managers container with Synapse and rules manager."""
    return make_test_managers(
        synapse=mock_synapse_manager, rules_manager=mock_rules_manager
    )


# ============================================================================
# sync_synapse() — additional edge cases
# ============================================================================


@pytest.mark.asyncio
class TestSyncSharedRulesEdgeCases:
    """Additional sync_synapse edge-case tests (Phase 9.5)."""

    async def test_sync_synapse_when_rules_manager_none(
        self, mock_project_root: Path, mock_synapse_manager: MagicMock
    ) -> None:
        """Sync succeeds when rules_manager is None (no reindex)."""
        managers = make_test_managers(synapse=mock_synapse_manager)
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_impl.get_managers",
                return_value=managers,
            ),
            patch(
                "cortex.tools.synapse_tools_helpers.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
            patch(
                "cortex.managers.manager_utils.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
        ):
            result_str = await sync_synapse(pull=True, push=False)
        result = json.loads(result_str)
        assert result["status"] == "success"

    async def test_sync_synapse_reindex_not_triggered_when_no_changes(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: ManagersDict,
    ) -> None:
        """When reindex_triggered is False, index_rules not called."""
        # Arrange: sync returns without reindex
        result_no_reindex = SynapseSyncResult(
            status=OperationStatus.SUCCESS,
            pulled=True,
            pushed=False,
            changes=SyncChanges(added=[], modified=[], deleted=[]),
            reindex_triggered=False,
            last_sync="2026-01-04T10:30:00Z",
        )
        synapse_mock = cast(MagicMock, mock_managers_with_synapse.synapse)
        synapse_mock.sync_synapse = AsyncMock(return_value=result_no_reindex)
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_impl.get_managers",
                return_value=mock_managers_with_synapse,
            ),
            patch(
                "cortex.tools.synapse_tools_helpers.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
            patch(
                "cortex.managers.manager_utils.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
        ):
            await sync_synapse(pull=True, push=False)
        rules_mock = cast(MagicMock, mock_managers_with_synapse.rules_manager)
        rules_mock.index_rules.assert_not_called()


# ============================================================================
# update_synapse() — content_type branches
# ============================================================================


@pytest.mark.asyncio
class TestUpdateSynapseContentType:
    """Tests for update_synapse(content_type=rule|prompt) MCP tool."""

    async def test_update_synapse_rule_via_content_type(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: ManagersDict,
    ) -> None:
        """update_synapse(content_type='rule') calls update_synapse_rule_impl."""
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_impl.get_managers",
                return_value=mock_managers_with_synapse,
            ),
            patch(
                "cortex.tools.synapse_tools_helpers.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
            patch(
                "cortex.managers.manager_utils.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
        ):
            result_str = await update_synapse(
                content_type="rule",
                category="python",
                file="style.md",
                content="# Style",
                commit_message="Update",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        synapse_mock = cast(MagicMock, mock_managers_with_synapse.synapse)
        synapse_mock.update_synapse_rule.assert_called_once()

    async def test_update_synapse_prompt_via_content_type(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: ManagersDict,
    ) -> None:
        """update_synapse(content_type='prompt') calls update_synapse_prompt_impl."""
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_impl.get_managers",
                return_value=mock_managers_with_synapse,
            ),
            patch(
                "cortex.tools.synapse_tools_helpers.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
            patch(
                "cortex.managers.manager_utils.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
        ):
            result_str = await update_synapse(
                content_type="prompt",
                category="general",
                file="implement.md",
                content="# Implement",
                commit_message="Update prompt",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        synapse_mock = cast(MagicMock, mock_managers_with_synapse.synapse)
        synapse_mock.update_synapse_prompt.assert_called_once()

    async def test_update_synapse_prompt_not_initialized(
        self, mock_project_root: Path
    ) -> None:
        """update_synapse fails when Synapse not initialized."""
        managers = make_test_managers()
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_impl.get_managers",
                return_value=managers,
            ),
        ):
            result_str = await update_synapse(
                content_type="prompt",
                category="general",
                file="test.md",
                content="x",
                commit_message="test",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "not initialized" in result["error"]


# ============================================================================
# get_synapse_rules() — edge cases
# ============================================================================


@pytest.mark.asyncio
class TestGetRulesWithContextEdgeCases:
    """Additional get_synapse_rules edge-case tests (Phase 9.5)."""

    async def test_get_synapse_rules_exception_returns_error_json(
        self, mock_project_root: Path
    ) -> None:
        """When execute_rules_with_context raises, return error JSON."""
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_helpers.execute_rules_with_context",
                new=AsyncMock(side_effect=ValueError("Rules engine failed")),
            ),
        ):
            result_str = await get_synapse_rules(
                task_description="test",
                max_tokens=1000,
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "Rules engine failed" in result["error"]
        assert result["error_type"] == "ValueError"

    async def test_get_synapse_rules_with_empty_task_description_via_get_synapse(
        self, mock_project_root: Path
    ) -> None:
        """get_synapse(content_type='rules', task_description='') returns error."""
        from cortex.tools.synapse_tools import get_synapse

        with patch(
            "cortex.tools.synapse_tools_impl.get_project_root",
            return_value=mock_project_root,
        ):
            result_str = await get_synapse(
                content_type="rules",
                task_description="",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "task_description required" in result["error"]

    async def test_get_synapse_rules_with_whitespace_task_description(
        self, mock_project_root: Path
    ) -> None:
        """get_synapse(content_type='rules', task_description='   ') returns error."""
        from cortex.tools.synapse_tools import get_synapse

        with patch(
            "cortex.tools.synapse_tools_impl.get_project_root",
            return_value=mock_project_root,
        ):
            result_str = await get_synapse(
                content_type="rules",
                task_description="   ",
            )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert "task_description required" in result["error"]


# ============================================================================
# update_synapse_rule / update_synapse_prompt wrappers
# ============================================================================


@pytest.mark.asyncio
class TestUpdateWrappers:
    """Test update_synapse_rule and update_synapse_prompt call update_synapse."""

    async def test_update_synapse_rule_wrapper_calls_update_synapse(
        self,
        mock_project_root: Path,
        mock_managers_with_synapse: ManagersDict,
    ) -> None:
        """update_synapse_rule delegates to update_synapse(content_type='rule')."""
        with (
            patch(
                "cortex.tools.synapse_tools_impl.get_project_root",
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.synapse_tools_impl.get_managers",
                return_value=mock_managers_with_synapse,
            ),
            patch(
                "cortex.tools.synapse_tools_helpers.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
            patch(
                "cortex.managers.manager_utils.get_manager",
                new=AsyncMock(side_effect=_get_manager_helper),
            ),
        ):
            result_str = await update_synapse_rule(
                category="python",
                file="x.md",
                content="c",
                commit_message="m",
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        synapse_mock = cast(MagicMock, mock_managers_with_synapse.synapse)
        synapse_mock.update_synapse_rule.assert_called_once_with(
            category="python", file="x.md", content="c", commit_message="m"
        )
