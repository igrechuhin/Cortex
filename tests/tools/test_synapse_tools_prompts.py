import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.types import ManagersDict
from cortex.tools.synapse_tools import get_synapse_prompts, update_synapse_prompt
from tests.helpers.managers import make_test_managers


def _get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
    return getattr(mgrs, key)


@pytest.fixture
def mock_synapse_manager_for_prompts() -> MagicMock:
    manager = MagicMock()
    manager.load_prompts_manifest = AsyncMock(return_value=True)
    manager.load_prompts_category = AsyncMock(
        return_value=[
            {
                "file": "refactor.md",
                "name": "Refactor",
                "category": "python",
                "description": "Refactor template",
                "keywords": ["refactor"],
            }
        ]
    )
    manager.get_all_prompts = AsyncMock(
        return_value=[
            {
                "file": "code-review.md",
                "name": "Code Review",
                "category": "general",
                "description": "Checklist",
                "keywords": ["review"],
            }
        ]
    )
    manager.get_prompt_categories = MagicMock(return_value=["general", "python"])
    manager.update_synapse_prompt = AsyncMock(
        return_value={"status": "success", "commit_sha": "abc123", "type": "prompt"}
    )
    return manager


@pytest.mark.asyncio
class TestSynapsePromptsTools:
    async def test_get_synapse_prompts_when_not_initialized_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        managers = make_test_managers()
        with (
            patch("cortex.tools.synapse_tools.get_project_root", return_value=tmp_path),
            patch("cortex.tools.synapse_tools.get_managers", return_value=managers),
        ):
            # Act
            result_str = await get_synapse_prompts()
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "not initialized" in result["error"]

    async def test_get_synapse_prompts_when_category_returns_category_response(
        self, tmp_path: Path, mock_synapse_manager_for_prompts: MagicMock
    ) -> None:
        # Arrange
        managers = make_test_managers(synapse=mock_synapse_manager_for_prompts)
        with (
            patch("cortex.tools.synapse_tools.get_project_root", return_value=tmp_path),
            patch("cortex.tools.synapse_tools.get_managers", return_value=managers),
            patch(
                "cortex.tools.synapse_tools.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_synapse_prompts(category="python")
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"
        assert result["category"] == "python"
        assert result["total_count"] == 1
        mock_synapse_manager_for_prompts.load_prompts_manifest.assert_awaited_once()
        mock_synapse_manager_for_prompts.load_prompts_category.assert_awaited_once_with(
            "python"
        )

    async def test_get_synapse_prompts_when_no_category_returns_all_prompts_response(
        self, tmp_path: Path, mock_synapse_manager_for_prompts: MagicMock
    ) -> None:
        # Arrange
        managers = make_test_managers(synapse=mock_synapse_manager_for_prompts)
        with (
            patch("cortex.tools.synapse_tools.get_project_root", return_value=tmp_path),
            patch("cortex.tools.synapse_tools.get_managers", return_value=managers),
            patch(
                "cortex.tools.synapse_tools.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_synapse_prompts()
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"
        assert result["categories"] == ["general", "python"]
        assert result["total_count"] == 1
        mock_synapse_manager_for_prompts.get_all_prompts.assert_awaited_once()

    async def test_update_synapse_prompt_when_not_initialized_returns_error(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        managers = make_test_managers()
        with (
            patch("cortex.tools.synapse_tools.get_project_root", return_value=tmp_path),
            patch("cortex.tools.synapse_tools.get_managers", return_value=managers),
        ):
            # Act
            result_str = await update_synapse_prompt(
                category="general",
                file="code-review.md",
                content="x",
                commit_message="msg",
            )
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "not initialized" in result["error"]

    async def test_update_synapse_prompt_when_initialized_returns_success(
        self, tmp_path: Path, mock_synapse_manager_for_prompts: MagicMock
    ) -> None:
        # Arrange
        managers = make_test_managers(synapse=mock_synapse_manager_for_prompts)
        with (
            patch("cortex.tools.synapse_tools.get_project_root", return_value=tmp_path),
            patch("cortex.tools.synapse_tools.get_managers", return_value=managers),
            patch(
                "cortex.tools.synapse_tools.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await update_synapse_prompt(
                category="general",
                file="code-review.md",
                content="# Content",
                commit_message="Update prompt",
            )
            result = json.loads(result_str)

        # Assert
        assert result["status"] == "success"
        mock_synapse_manager_for_prompts.update_synapse_prompt.assert_awaited_once()
