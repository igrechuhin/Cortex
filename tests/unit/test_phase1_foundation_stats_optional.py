from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.lazy_manager import LazyManager
from cortex.tools import phase1_foundation_stats
from tests.helpers.managers import make_test_managers


@pytest.mark.asyncio
class TestPhase1FoundationStatsOptional:
    async def test_build_refactoring_history_when_executor_missing_returns_none(
        self,
    ) -> None:
        # Arrange
        mgrs = make_test_managers(refactoring_executor=None)

        # Act
        result = await phase1_foundation_stats._build_refactoring_history_dict(  # noqa: SLF001
            mgrs, refactoring_days=7
        )

        # Assert
        assert result is None

    async def test_build_refactoring_history_when_lazy_executor_returns_history_dict(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        exec_item = MagicMock(created_at=datetime.now().isoformat())
        history = MagicMock(
            executions=[exec_item],
            total_executions=1,
            successful=1,
            rolled_back=0,
        )
        refactoring_executor = MagicMock()
        refactoring_executor.get_execution_history = AsyncMock(return_value=history)

        async def _factory():
            return refactoring_executor

        lazy = LazyManager(_factory, name="refactoring_executor")
        mgrs = make_test_managers(refactoring_executor=lazy)

        # Act
        result = await phase1_foundation_stats._build_refactoring_history_dict(  # noqa: SLF001
            mgrs, refactoring_days=30
        )

        # Assert
        assert result is not None
        assert result["total_refactorings"] == 1
        assert isinstance(result["recent"], list)

    async def test_add_optional_stats_includes_refactoring_history(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        base: dict[str, object] = {"status": "success"}
        fake_mgrs = make_test_managers()
        with (
            patch(
                "cortex.tools.phase1_foundation_stats.initialization.get_project_root",
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.phase1_foundation_stats.initialization.get_managers",
                return_value=fake_mgrs,
            ),
            patch(
                "cortex.tools.phase1_foundation_stats._build_refactoring_history_dict",
                new=AsyncMock(return_value={"total_refactorings": 0, "recent": []}),
            ),
        ):
            # Act
            result = await phase1_foundation_stats._add_optional_stats(  # noqa: SLF001
                base,
                include_token_budget=False,
                include_refactoring_history=True,
                project_root=str(tmp_path),
                total_tokens=0,
                refactoring_days=7,
            )

        # Assert
        assert result is not None
        assert "refactoring_history" in result
