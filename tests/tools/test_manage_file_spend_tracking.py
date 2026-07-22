"""manage_file runtime spend-tracking: single-increment-per-call verification.

Covers the plan Risks item: "add a unit test asserting a single manage_file
call increments spend exactly once" (no double counting across the read and
write flows wired in crud_flow.py).
"""

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.session_logger import get_session_log_path, read_session_log
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.types import ManagersDict
from cortex.tools.files.crud_operations import manage_file
from tests.helpers.managers import make_test_managers
from tests.helpers.path_helpers import ensure_test_cortex_structure

_ENV_KEY = "CORTEX_SESSION_ID"


def _current_spend(project_root: Path) -> int:
    session_log = read_session_log(get_session_log_path(project_root))
    return session_log.cumulative_spend_tokens if session_log else 0


async def _seed_active_context_metadata(
    metadata_index: MetadataIndex,
    memory_bank_dir: Path,
    content: str,
    token_counter: TokenCounter,
) -> None:
    """Pre-populate metadata so a subsequent read can include_metadata."""
    await metadata_index.update_file_metadata(
        file_name="activeContext.md",
        path=memory_bank_dir / "activeContext.md",
        exists=True,
        size_bytes=len(content.encode("utf-8")),
        token_count=token_counter.count_tokens(content),
        content_hash="sha256:test",
        sections=[],
    )


@contextmanager
def _patched_manage_file_env(managers: ManagersDict, tmp_path: Path) -> Generator[None]:
    """Patch manage_file's manager/project-root resolution for the duration."""
    with patch.multiple(
        "cortex.tools.files.manage_file_helpers",
        get_managers=AsyncMock(return_value=managers),
        get_or_resolve_project_root=AsyncMock(return_value=tmp_path),
    ):
        yield


@pytest.fixture
def isolated_session_id() -> Generator[None]:
    """Give each test its own session log so spend totals don't leak across tests."""
    original = os.environ.get(_ENV_KEY)
    os.environ[_ENV_KEY] = f"spend_tracking_{id(object())}"
    yield
    if original:
        os.environ[_ENV_KEY] = original
    else:
        _ = os.environ.pop(_ENV_KEY, None)


@pytest.mark.asyncio
@pytest.mark.timeout(15)
class TestManageFileSpendSingleIncrement:
    """A single manage_file call records spend exactly once."""

    async def test_write_call_increments_spend_exactly_once(
        self, tmp_path: Path, isolated_session_id: None
    ) -> None:
        """One write with include_metadata off still records spend exactly once."""
        # Arrange
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        _ = (memory_bank_dir / "activeContext.md").write_text("# Active Context\n")
        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        version_manager = VersionManager(tmp_path)
        token_counter = TokenCounter()
        managers = make_test_managers(
            fs=fs_manager,
            index=metadata_index,
            tokens=token_counter,
            versions=version_manager,
        )
        content = "# Active Context\n\n## Current Focus\n\nWorking on the guard.\n"
        assert _current_spend(tmp_path) == 0

        with _patched_manage_file_env(managers, tmp_path):
            # Act
            result_str = await manage_file(
                file_name="activeContext.md",
                operation="write",
                content=content,
                change_description="test spend tracking",
            )

        # Assert - write response's own "tokens" field is the single source of
        # truth for what should have been recorded exactly once (write may
        # prepend classification metadata, changing the token count from the
        # raw input content).
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert _current_spend(tmp_path) == result["tokens"]

    async def test_read_with_metadata_increments_spend_exactly_once(
        self, tmp_path: Path, isolated_session_id: None
    ) -> None:
        """One read with include_metadata records spend exactly once (no double count)."""
        # Arrange
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        content = "# Active Context\n\n## Current Focus\n\nWorking on the guard.\n"
        _ = (memory_bank_dir / "activeContext.md").write_text(content)

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        token_counter = TokenCounter()
        await _seed_active_context_metadata(
            metadata_index, memory_bank_dir, content, token_counter
        )
        managers = make_test_managers(
            fs=fs_manager,
            index=metadata_index,
            tokens=token_counter,
            versions=AsyncMock(),
        )
        expected_tokens = token_counter.count_tokens(content)
        assert _current_spend(tmp_path) == 0

        with _patched_manage_file_env(managers, tmp_path):
            # Act
            result_str = await manage_file(
                file_name="activeContext.md",
                operation="read",
                include_metadata=True,
            )

        # Assert
        assert '"status": "success"' in result_str
        assert _current_spend(tmp_path) == expected_tokens

    async def test_read_without_metadata_records_no_spend(
        self, tmp_path: Path, isolated_session_id: None
    ) -> None:
        """Plain read (no include_metadata) does not record spend."""
        # Arrange
        memory_bank_dir = ensure_test_cortex_structure(tmp_path)
        content = "# Active Context\n"
        _ = (memory_bank_dir / "activeContext.md").write_text(content)

        fs_manager = FileSystemManager(tmp_path)
        metadata_index = MetadataIndex(tmp_path)
        _ = await metadata_index.load()
        managers = make_test_managers(
            fs=fs_manager,
            index=metadata_index,
            tokens=TokenCounter(),
            versions=AsyncMock(),
        )
        assert _current_spend(tmp_path) == 0

        with _patched_manage_file_env(managers, tmp_path):
            # Act
            result_str = await manage_file(
                file_name="activeContext.md",
                operation="read",
            )

        # Assert
        assert '"status": "success"' in result_str
        assert _current_spend(tmp_path) == 0
