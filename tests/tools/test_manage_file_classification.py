import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.tools.files.operations import manage_file
from cortex.tools.plans.append_entry_dispatcher import append_entry_impl
from tests.helpers.managers import make_test_managers


def _prepare_memory_bank_file(tmp_path: Path) -> None:
    memory_bank = tmp_path / ".cortex" / "memory-bank"
    _ = memory_bank.mkdir(parents=True)
    active = memory_bank / "activeContext.md"
    _ = active.write_text(
        """<!-- memory_type: milestone -->
completed migration

<!-- memory_type: problem -->
error blocked release
""",
        encoding="utf-8",
    )


async def _run_read_by_type(tmp_path: Path) -> str:
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.name = "activeContext.md"
    mock_fs = AsyncMock()
    mock_fs.construct_safe_path = MagicMock(return_value=mock_path)
    mock_managers_dict = {
        "fs": mock_fs,
        "index": AsyncMock(),
        "tokens": MagicMock(),
        "versions": AsyncMock(),
    }
    payload = json.dumps({"file_name": "activeContext.md", "memory_type": "milestone"})
    with patch(
        "cortex.tools.files.manage_file_helpers.get_managers",
        new_callable=AsyncMock,
        return_value=make_test_managers(**mock_managers_dict),
    ):
        with patch(
            "cortex.tools.files.manage_file_helpers.get_or_resolve_project_root",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ):
            result = await manage_file(
                file_name="activeContext.md",
                operation="read_by_type",
                content=payload,
            )
    return result


@pytest.mark.asyncio
async def test_manage_file_read_by_type_filters_entries(tmp_path: Path) -> None:
    _prepare_memory_bank_file(tmp_path)
    result = await _run_read_by_type(tmp_path)
    parsed = json.loads(result)
    assert parsed["status"] == "success"
    assert len(parsed["entries"]) == 1
    assert parsed["entries"][0]["memory_type"] == "milestone"


@pytest.mark.asyncio
async def test_append_entry_impl_respects_skip_classification() -> None:
    with patch(
        "cortex.tools.plans.completion.append_progress_entry_impl",
        new_callable=AsyncMock,
        return_value='{"status":"success"}',
    ) as append_mock:
        _ = await append_entry_impl(
            operation="progress",
            date_str="2026-04-14",
            entry_text="plain status update",
            skip_classification=True,
        )
    assert append_mock.await_count == 1
    assert append_mock.await_args is not None
    args = append_mock.await_args.args
    assert "<!-- memory_type:" not in args[1]
