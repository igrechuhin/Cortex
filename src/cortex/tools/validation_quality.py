"""Quality validation operations for Memory Bank files."""

import json
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics


async def validate_quality_single_file(
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    quality_metrics: QualityMetrics,
    root: Path,
    file_name: str,
) -> str:
    """Calculate quality score for a single file."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        file_path = fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return json.dumps(
            {"status": "error", "error": f"Invalid file name: {e}"}, indent=2
        )
    if not file_path.exists():
        return json.dumps(
            {"status": "error", "error": f"File {file_name} does not exist"}, indent=2
        )
    content, _ = await fs_manager.read_file(file_path)
    file_metadata = await metadata_index.get_file_metadata(file_name)
    metadata = file_metadata or {}
    score = await quality_metrics.calculate_file_score(file_name, content, metadata)
    return json.dumps(
        {
            "status": "success",
            "check_type": "quality",
            "file_name": file_name,
            "score": score,
        },
        indent=2,
    )


async def validate_quality_all_files(
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    quality_metrics: QualityMetrics,
    duplication_detector: DuplicationDetector,
    root: Path,
) -> str:
    """Calculate overall quality score for all files."""
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    all_files_content: dict[str, str] = {}
    files_metadata: dict[str, dict[str, object]] = {}
    for md_file in memory_bank_dir.glob("*.md"):
        if md_file.is_file():
            content, _ = await fs_manager.read_file(md_file)
            all_files_content[md_file.name] = content
            file_meta = await metadata_index.get_file_metadata(md_file.name)
            files_metadata[md_file.name] = file_meta or {}
    duplication_data = await duplication_detector.scan_all_files(all_files_content)
    overall_score = await quality_metrics.calculate_overall_score(
        all_files_content, files_metadata, duplication_data
    )
    result: dict[str, object] = {"status": "success", "check_type": "quality"}
    for key, value in overall_score.items():
        if key != "status":
            result[key] = value
        else:
            result["health_status"] = value
    return json.dumps(result, indent=2)


async def handle_quality_validation(
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    quality_metrics: QualityMetrics,
    duplication_detector: DuplicationDetector,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle quality validation routing.

    Args:
        fs_manager: File system manager
        metadata_index: Metadata index instance
        quality_metrics: Quality metrics instance
        duplication_detector: Duplication detector instance
        root: Project root path
        file_name: Optional specific file to validate

    Returns:
        JSON string with quality validation results
    """
    if file_name:
        return await validate_quality_single_file(
            fs_manager, metadata_index, quality_metrics, root, file_name
        )
    else:
        return await validate_quality_all_files(
            fs_manager, metadata_index, quality_metrics, duplication_detector, root
        )
