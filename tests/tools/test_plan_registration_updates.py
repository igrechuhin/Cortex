"""Registration updates preserve roadmap position, content, and failed writes."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.register import register_plan_in_roadmap
from cortex.tools.plans.register_models import RegisterPlanResult
from cortex.tools.plans.register_helpers import register_plan_entry


@pytest.fixture
def roadmap(tmp_path: Path) -> Path:
    memory = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    plans = get_cortex_path(tmp_path, CortexResourceType.PLANS)
    memory.mkdir(parents=True)
    plans.mkdir(parents=True)
    _ = (plans / "existing.md").write_text(
        "---\ntitle: Existing\nstatus: PENDING\n---\n\n## Goal\nKeep state.\n"
    )
    path = memory / "roadmap.md"
    _ = path.write_text(
        "# Roadmap\n\n## Blockers (ASAP Priority)\n\n- Unrelated blocker\n\n"
        + "## Pending plans (from .cortex/plans)\n\n- Before\n"
        + "- **Existing** - PENDING - Original. Plan: .cortex/plans/existing.md\n"
        + "- After\n\n## Unrelated section\n\nKeep this text.\n"
    )
    return path


async def register(tmp_path: Path, description: str, status: str) -> RegisterPlanResult:
    with patch(
        "cortex.tools.plans.register.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    ):
        raw = await register_plan_in_roadmap(
            plan_title="Existing",
            description=description,
            status=status,
            section="pending",
            plan_file_name="existing.md",
        )
    return RegisterPlanResult.model_validate_json(raw)


@pytest.mark.asyncio
async def test_update_then_replay_preserves_roadmap(
    tmp_path: Path, roadmap: Path
) -> None:
    # Arrange
    original = roadmap.read_text()
    expected = original.replace("PENDING - Original.", "IN PROGRESS - Revised.")
    # Act
    result = await register(tmp_path, "Revised.", "IN PROGRESS")
    replay = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "success"
    assert replay.status == "success"
    assert roadmap.read_text() == expected
    assert roadmap.read_text().count(".cortex/plans/existing.md") == 1


@pytest.mark.asyncio
async def test_unchanged_registration_succeeds(tmp_path: Path, roadmap: Path) -> None:
    # Arrange
    original = roadmap.read_bytes()
    # Act
    result = await register(tmp_path, "Original.", "PENDING")
    # Assert
    assert result.status == "success"
    assert roadmap.read_bytes() == original


@pytest.mark.asyncio
async def test_failed_replacement_preserves_registration(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    original = roadmap.read_bytes()
    # Act
    with patch.object(Path, "replace", side_effect=OSError("replacement denied")):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "replacement denied" in result.error
    assert roadmap.read_bytes() == original
    assert sorted(path.name for path in roadmap.parent.iterdir()) == ["roadmap.md"]


@pytest.mark.asyncio
async def test_partial_write_failure_preserves_registration(
    tmp_path: Path,
    roadmap: Path,
) -> None:
    # Arrange
    original = roadmap.read_bytes()
    write_text = Path.write_text

    def fail_write(path: Path, content: str, encoding: str) -> None:
        _ = write_text(path, content[:10], encoding=encoding)
        raise OSError("disk full")

    # Act
    with patch.object(Path, "write_text", autospec=True, side_effect=fail_write):
        result = await register(tmp_path, "Revised.", "IN PROGRESS")
    # Assert
    assert result.status == "error"
    assert result.error is not None and "disk full" in result.error
    assert roadmap.read_bytes() == original


def test_pathless_replay_preserves_header() -> None:
    # Arrange
    original = "## Pending plans (from .cortex/plans)\n\n- **A** - PENDING - Work\n"
    # Act
    updated, line = register_plan_entry(original, "A", "Work", "PENDING", "pending")
    # Assert
    assert updated == original
    assert line == 3


def test_unknown_section_does_not_modify_roadmap() -> None:
    # Arrange
    original = "# Roadmap\n\n## Pending plans (from .cortex/plans)\n"
    # Act
    updated, line = register_plan_entry(original, "A", "Work", "PENDING", "unknown")
    # Assert
    assert updated == original
    assert line is None
