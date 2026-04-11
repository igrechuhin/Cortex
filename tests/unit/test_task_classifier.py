"""Tests for task type inference heuristics."""

from cortex.core.models import TaskType
from cortex.core.task_classifier import infer_task_type
from cortex.tools.context.scoped_context import extract_file_paths


def test_infer_task_type_uses_plan_text_hints() -> None:
    # Arrange
    plan = "Implement MCP resource and add pytest coverage for schema models."

    # Act
    types = infer_task_type(plan, files_touched=[])

    # Assert
    assert TaskType.MCP_RESOURCE in types
    assert TaskType.TEST in types
    assert TaskType.SCHEMA in types


def test_infer_task_type_uses_file_paths() -> None:
    # Arrange / Act
    types = infer_task_type(
        "No specific keywords.",
        files_touched=[
            "src/cortex/tools/foo.py",
            "tests/unit/test_foo.py",
            "docs/readme.md",
        ],
    )

    # Assert
    assert TaskType.MCP_TOOL in types
    assert TaskType.TEST in types
    assert TaskType.DOCUMENTATION in types
    assert TaskType.CORE_LOGIC in types


def test_infer_task_type_falls_back_to_all() -> None:
    # Arrange / Act
    types = infer_task_type("completely generic", files_touched=[])

    # Assert
    assert types == [TaskType.ALL]


def test_extract_file_paths_finds_paths_in_plan_text() -> None:
    # Arrange
    plan = (
        "Implemented changes — files: src/cortex/core/models/_enums.py, "
        "tests/unit/test_classifier.py, docs/api/tools.md"
    )

    # Act
    paths = extract_file_paths(plan)

    # Assert
    assert "src/cortex/core/models/_enums.py" in paths
    assert "tests/unit/test_classifier.py" in paths
    assert "docs/api/tools.md" in paths


def test_extract_file_paths_enables_file_path_classification() -> None:
    # Arrange — TypeScript file mentioned in plan text should yield CORE_LOGIC
    plan = "Updated UI — files: src/components/Button.tsx, src/api/handler.go"

    # Act
    types = infer_task_type(plan, files_touched=extract_file_paths(plan))

    # Assert
    assert TaskType.CORE_LOGIC in types


def test_infer_task_type_non_python_source_files() -> None:
    # Arrange / Act — TypeScript and Go files should classify as CORE_LOGIC
    types = infer_task_type(
        "No keywords.",
        files_touched=["src/components/Button.tsx", "src/api/handler.go"],
    )

    # Assert
    assert TaskType.CORE_LOGIC in types
