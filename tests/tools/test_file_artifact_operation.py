"""Tests for manage_file file_artifact operation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from cortex.tools.files.artifact_operations import file_artifact
from cortex.tools.files.operation_helpers import validate_manage_file_operation


def _read_json(result: str) -> dict[str, object]:
    return json.loads(result)


async def test_file_artifact_writes_review_report(tmp_path: Path) -> None:
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )

    result = _read_json(
        await file_artifact(
            memory_bank_dir=memory_bank_dir,
            artifact_type="review_report",
            title="Auth Review",
            content="review content",
            tags=["security"],
        )
    )

    assert result["status"] == "success"
    output_path = Path(str(result["path"]))
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "review content"
    assert output_path.parent.name == "reviews"
    assert output_path.name.startswith("review-auth-review-")
    active_context = (memory_bank_dir / "activeContext.md").read_text(encoding="utf-8")
    assert "[Auth Review](reviews/" in active_context


async def test_file_artifact_invalidates_context_resource_cache(tmp_path: Path) -> None:
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )
    with patch(
        "cortex.tools.optimization.handlers.invalidate_context_resource_cache"
    ) as inv:
        result = _read_json(
            await file_artifact(
                memory_bank_dir=memory_bank_dir,
                artifact_type="review_report",
                title="Cache Test",
                content="body",
                tags=None,
            )
        )
    assert result["status"] == "success"
    inv.assert_called_once()


async def test_file_artifact_dedupes_duplicate_titles(tmp_path: Path) -> None:
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Completed Work (2026-04-07)\n\n",
        encoding="utf-8",
    )

    first = _read_json(
        await file_artifact(
            memory_bank_dir=memory_bank_dir,
            artifact_type="session_analysis",
            title="Weekly Session",
            content="one",
            tags=None,
        )
    )
    second = _read_json(
        await file_artifact(
            memory_bank_dir=memory_bank_dir,
            artifact_type="session_analysis",
            title="Weekly Session",
            content="two",
            tags=None,
        )
    )

    first_path = Path(str(first["path"]))
    second_path = Path(str(second["path"]))
    assert first_path != second_path
    assert second_path.stem.endswith("-2")


def test_validate_manage_file_operation_file_artifact_no_filename() -> None:
    parsed_op, error = validate_manage_file_operation(
        operation="file_artifact",
        file_name=None,
    )

    assert error is None
    assert parsed_op is not None
    assert parsed_op.value == "file_artifact"
