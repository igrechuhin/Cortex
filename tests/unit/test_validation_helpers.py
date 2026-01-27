from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.tools.validation_helpers import (
    create_invalid_check_type_error,
    create_validation_error_response,
    generate_duplication_fixes,
    read_all_memory_bank_files,
)


@pytest.mark.asyncio
async def test_read_all_memory_bank_files_reads_markdown_files(tmp_path) -> None:
    # Arrange
    memory_bank_dir = tmp_path / ".cortex" / "memory-bank"
    memory_bank_dir.mkdir(parents=True, exist_ok=True)
    md1 = memory_bank_dir / "a.md"
    md2 = memory_bank_dir / "b.md"
    _ = md1.write_text("# A", encoding="utf-8")
    _ = md2.write_text("# B", encoding="utf-8")
    # Also create a directory that matches the glob but isn't a file
    (memory_bank_dir / "not-a-file.md").mkdir(parents=True, exist_ok=True)

    fs_manager = MagicMock()

    async def _read_file(path):
        name = path.name
        if name == "a.md":
            return "# A", "h1"
        return "# B", "h2"

    fs_manager.read_file = AsyncMock(side_effect=_read_file)

    # Act
    content = await read_all_memory_bank_files(fs_manager, tmp_path)

    # Assert
    assert content["a.md"] == "# A"
    assert content["b.md"] == "# B"
    assert fs_manager.read_file.await_count == 2


def test_generate_duplication_fixes_creates_transclusion_suggestions() -> None:
    # Arrange
    duplications_data = {
        "exact_duplicates": [{"files": ["a.md", "b.md"]}],
        "similar_content": [{"files": ["c.md", "d.md"]}],
    }

    # Act
    fixes = generate_duplication_fixes(duplications_data)

    # Assert
    assert len(fixes) == 2
    assert fixes[0]["files"] == ["a.md", "b.md"]
    assert fixes[1]["files"] == ["c.md", "d.md"]


def test_generate_duplication_fixes_ignores_invalid_entries() -> None:
    # Arrange
    duplications_data = {
        "exact_duplicates": [{"files": ["only-one.md"]}, "not-a-dict"],
        "similar_content": [{"files": "not-a-list"}],
    }

    # Act
    fixes = generate_duplication_fixes(duplications_data)

    # Assert
    assert fixes == []


def test_generate_duplication_fixes_when_exact_not_list_still_processes_similar() -> (
    None
):
    # Arrange
    duplications_data = {
        "exact_duplicates": "not-a-list",
        "similar_content": [
            {"files": ["a.md", "b.md"]},
            {"files": ["only-one.md"]},
            "not-a-dict",
        ],
    }

    # Act
    fixes = generate_duplication_fixes(duplications_data)

    # Assert
    assert len(fixes) == 1
    assert fixes[0]["files"] == ["a.md", "b.md"]


def test_generate_duplication_fixes_when_similar_not_list_returns_only_exact_fixes() -> (  # noqa: E501
    None
):
    # Arrange
    duplications_data = {
        "exact_duplicates": [{"files": ["a.md", "b.md"]}],
        "similar_content": "not-a-list",
    }

    # Act
    fixes = generate_duplication_fixes(duplications_data)

    # Assert
    assert len(fixes) == 1
    assert fixes[0]["files"] == ["a.md", "b.md"]


def test_create_invalid_check_type_error_includes_valid_types() -> None:
    # Arrange
    check_type = "nope"

    # Act
    result = create_invalid_check_type_error(check_type)

    # Assert
    assert '"status": "error"' in result
    assert "Invalid check_type" in result
    assert "roadmap_sync" in result


def test_create_validation_error_response_includes_error_type() -> None:
    # Arrange
    error = ValueError("boom")

    # Act
    result = create_validation_error_response(error)

    # Assert
    assert '"status": "error"' in result
    assert "boom" in result
    assert "ValueError" in result
