"""Shared fixtures/helpers for validation operations tests."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from cortex.core.models import DetailedFileMetadata, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path


def _model_dump_mock(payload: ModelDict) -> MagicMock:
    """Return MagicMock with model_dump() preconfigured."""
    return MagicMock(model_dump=MagicMock(return_value=payload))


def _quality_single_file_score_payload() -> ModelDict:
    """Return score payload for quality single-file success tests."""
    return {
        "file_name": "projectBrief.md",
        "score": 85,
        "grade": "B",
        "validation": {"valid": True, "errors": [], "warnings": []},
        "freshness": 90,
        "structure": 80,
    }


def _quality_single_file_metadata(path: str) -> DetailedFileMetadata:
    """Return metadata object for quality single-file success tests."""
    return DetailedFileMetadata(
        path=path,
        exists=True,
        size_bytes=0,
        token_count=100,
        token_model="",
        last_modified="",
        content_hash="",
    )


def setup_schema_all_files_success(
    tmp_path: Path, mock_fs_manager: MagicMock
) -> MagicMock:
    """Prepare filesystem and validator mocks for schema all-files success path."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    _ = memory_bank_dir.mkdir(parents=True)
    _ = (memory_bank_dir / "file1.md").write_text("# Content 1\n")
    _ = (memory_bank_dir / "file2.md").write_text("# Content 2\n")
    mock_fs_manager.read_file = AsyncMock(
        side_effect=[("# Content 1\n", None), ("# Content 2\n", None)]
    )
    validator = MagicMock()
    validator.validate_file = AsyncMock(
        side_effect=[
            _model_dump_mock({"valid": True, "errors": [], "warnings": []}),
            _model_dump_mock(
                {"valid": False, "errors": ["Missing section"], "warnings": []}
            ),
        ]
    )
    return validator


def setup_validate_duplications_with_fixes(
    tmp_path: Path, mock_fs_manager: MagicMock
) -> tuple[MagicMock, MagicMock]:
    """Prepare detector/config mocks for duplication-fixes test."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    mock_fs_manager.read_file = AsyncMock(return_value=("Content", None))
    detector = MagicMock()
    duplication_payload = {
        "duplicates_found": 1,
        "exact_duplicates": [
            {"files": ["file1.md", "file2.md"], "content": "Duplicate"}
        ],
        "similar_content": [],
    }
    detector.scan_all_files = AsyncMock(
        return_value=MagicMock(
            model_dump=MagicMock(return_value=duplication_payload),
            duplicates_found=1,
        )
    )
    config = MagicMock()
    config.get_duplication_threshold.return_value = 0.85
    return detector, config


def setup_validate_quality_single_file_success(
    tmp_path: Path, mock_fs_manager: MagicMock
) -> tuple[MagicMock, MagicMock]:
    """Prepare mocks for validate_quality_single_file success test."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    test_file = memory_bank_dir / "projectBrief.md"
    _ = test_file.write_text("# Content\n")
    mock_fs_manager.construct_safe_path.return_value = test_file
    mock_fs_manager.read_file = AsyncMock(return_value=("# Content\n", None))
    mock_index = MagicMock()
    mock_index.get_file_metadata = AsyncMock(
        return_value=_quality_single_file_metadata(str(test_file))
    )
    mock_metrics = MagicMock()
    mock_metrics.calculate_file_score = AsyncMock(
        return_value=_model_dump_mock(_quality_single_file_score_payload())
    )
    return mock_index, mock_metrics


def setup_validate_quality_all_files_success(
    tmp_path: Path, mock_fs_manager: MagicMock
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Prepare mocks for validate_quality_all_files success test."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    _ = (memory_bank_dir / "file1.md").write_text("Content 1")
    _ = (memory_bank_dir / "file2.md").write_text("Content 2")
    mock_fs_manager.read_file = AsyncMock(
        side_effect=[("Content 1", None), ("Content 2", None)]
    )
    mock_index = MagicMock()
    mock_index.get_file_metadata = AsyncMock(side_effect=[{"tokens": 50}, {}])
    mock_metrics = MagicMock()
    mock_metrics.calculate_overall_score = AsyncMock(
        return_value=_model_dump_mock(
            {"overall_score": 80, "status": "healthy", "grade": "B", "breakdown": {}}
        )
    )
    mock_detector = MagicMock()
    mock_detector.scan_all_files = AsyncMock(
        return_value=MagicMock(
            model_dump=MagicMock(return_value={"duplicates_found": 0}),
            duplicates_found=0,
        )
    )
    return mock_index, mock_metrics, mock_detector


def setup_handle_quality_validation_with_file_mocks(tmp_path: Path) -> dict[str, Any]:
    """Build managers dict for handle_quality_validation(file) success test."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    test_file = memory_bank_dir / "test.md"
    _ = test_file.write_text("Content")
    managers: dict[str, Any] = {
        "fs_manager": MagicMock(),
        "metadata_index": MagicMock(),
        "quality_metrics": MagicMock(),
        "duplication_detector": MagicMock(),
    }
    managers["fs_manager"].construct_safe_path.return_value = test_file
    managers["fs_manager"].read_file = AsyncMock(return_value=("Content", None))
    managers["metadata_index"].get_file_metadata = AsyncMock(return_value={})
    managers["quality_metrics"].calculate_file_score = AsyncMock(
        return_value=_model_dump_mock(
            {
                "file_name": "test.md",
                "score": 85,
                "grade": "B",
                "validation": {"valid": True, "errors": [], "warnings": []},
                "freshness": 90,
                "structure": 80,
            }
        )
    )
    return managers


def setup_handle_quality_validation_all_files_mocks(tmp_path: Path) -> dict[str, Any]:
    """Build managers dict for handle_quality_validation(all-files) success test."""
    _ = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK).mkdir(parents=True)
    managers: dict[str, Any] = {
        "fs_manager": MagicMock(),
        "metadata_index": MagicMock(),
        "quality_metrics": MagicMock(),
        "duplication_detector": MagicMock(),
    }
    managers["fs_manager"].read_file = AsyncMock(return_value=("Content", None))
    managers["metadata_index"].get_file_metadata = AsyncMock(return_value={})
    managers["quality_metrics"].calculate_overall_score = AsyncMock(
        return_value=_model_dump_mock(
            {"overall_score": 80, "status": "healthy", "grade": "B", "breakdown": {}}
        )
    )
    managers["duplication_detector"].scan_all_files = AsyncMock(
        return_value=MagicMock(
            model_dump=MagicMock(return_value={"duplicates_found": 0}),
            duplicates_found=0,
        )
    )
    return managers


def setup_infrastructure_success_workspace(tmp_path: Path) -> None:
    """Create minimal files required for infrastructure success test."""
    github_dir = tmp_path / ".github" / "workflows"
    github_dir.mkdir(parents=True)
    _ = (github_dir / "quality.yml").write_text(
        "name: Test\njobs:\n  test:\n    steps:\n      - name: Test step"
    )
    synapse_dir = get_cortex_path(tmp_path, CortexResourceType.SYNAPSE)
    prompts_dir = synapse_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    _ = (prompts_dir / "commit.md").write_text(
        "# Commit\n\n1. **Test step**\n   Description"
    )
    scripts_dir = synapse_dir / "scripts" / "python"
    scripts_dir.mkdir(parents=True)
    _ = (scripts_dir / "check_file_sizes.py").write_text("# Script")
    _ = (scripts_dir / "check_function_lengths.py").write_text("# Script")


def setup_validation_managers_mock_values() -> tuple[MagicMock, list[MagicMock]]:
    """Prepare manager mocks for setup_validation_managers success test."""
    base_fs = MagicMock()
    base_index = MagicMock()
    manager_sequence = [
        base_fs,
        base_index,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    return base_fs, manager_sequence


def setup_timestamps_all_files_valid(
    tmp_path: Path, mock_fs_manager: MagicMock
) -> None:
    """Prepare filesystem mocks for valid all-files timestamp validation."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    _ = (memory_bank_dir / "activeContext.md").write_text(
        "# Active Context\n\n## Current Focus (2026-01-14T10:00)\n"
    )
    _ = (memory_bank_dir / "progress.md").write_text(
        "# Progress\n\n## 2026-01-14: Updates\n"
    )

    async def mock_list_files(_: Path) -> list[Path]:
        return [memory_bank_dir / "activeContext.md", memory_bank_dir / "progress.md"]

    mock_fs_manager.list_files = AsyncMock(side_effect=mock_list_files)
    mock_fs_manager.read_file = AsyncMock(
        side_effect=[
            ("# Active Context\n\n## Current Focus (2026-01-14)\n", None),
            ("# Progress\n\n## 2026-01-14: Updates\n", None),
        ]
    )


def setup_timestamps_all_files_with_violations(
    tmp_path: Path, mock_fs_manager: MagicMock
) -> None:
    """Prepare filesystem mocks for invalid all-files timestamp validation."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    _ = (memory_bank_dir / "progress.md").write_text(
        "# Progress\n\n- ✅ Feature (2026-01-13 12:00)\n"
    )
    _ = (memory_bank_dir / "roadmap.md").write_text(
        "# Roadmap\n\n- ✅ Feature (2026-01-13T12:00:00)\n"
    )

    async def mock_list_files(_: Path) -> list[Path]:
        return [memory_bank_dir / "progress.md", memory_bank_dir / "roadmap.md"]

    mock_fs_manager.list_files = AsyncMock(side_effect=mock_list_files)
    mock_fs_manager.read_file = AsyncMock(
        side_effect=[
            ("# Progress\n\n- ✅ Feature (2026-01-13 12:00)\n", None),
            ("# Roadmap\n\n- ✅ Feature (2026-01-13T12:00:00)\n", None),
        ]
    )


def setup_roadmap_sync_cwd_fallback_workspace(
    tmp_path: Path, wrong_root: Path, mock_fs_manager: MagicMock
) -> None:
    """Prepare workspace data for roadmap sync cwd-fallback tests."""
    memory_bank_dir = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
    memory_bank_dir.mkdir(parents=True)
    roadmap_content = "# Roadmap\n\n## Phase 1\nSee `src/module.py` for details.\n"
    _ = (memory_bank_dir / "roadmap.md").write_text(roadmap_content)
    src_dir = tmp_path / "src"
    _ = src_dir.mkdir()
    _ = (src_dir / "module.py").write_text("# Module\n")
    mock_fs_manager.read_file = AsyncMock(return_value=(roadmap_content, None))
    mock_fs_manager.project_root = wrong_root
    mock_fs_manager.memory_bank_dir = get_cortex_path(
        wrong_root, CortexResourceType.MEMORY_BANK
    )
