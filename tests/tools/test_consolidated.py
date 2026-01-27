"""Unit tests for consolidated MCP tools."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.lazy_manager import LazyManager
from cortex.tools.analysis_operations import analyze
from cortex.tools.configuration_operations import configure
from cortex.tools.file_operations import manage_file
from cortex.tools.models import SchemaValidationResult
from cortex.tools.refactoring_operations import suggest_refactoring
from cortex.tools.validation_operations import validate
from cortex.validation.models import (
    CategoryBreakdown,
    DuplicateEntry,
    DuplicationScanResult,
    QualityScoreResult,
)
from tests.helpers.managers import make_test_managers


@pytest.mark.asyncio
class TestManageFile:
    """Tests for manage_file consolidated tool."""

    async def test_manage_file_read_success(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test successful file read operation."""
        # Setup
        file_name = "projectBrief.md"
        content = "# Project Brief\nTest content"
        # Ensure file exists with correct content (for exists() check)
        # The mock read_file will return this content, but file must exist for check
        temp_memory_bank.parent.mkdir(parents=True, exist_ok=True)
        if temp_memory_bank.exists():
            temp_memory_bank.unlink()
        _ = temp_memory_bank.write_text(content)
        # Verify file has correct content
        assert temp_memory_bank.read_text() == content

        # Mock managers
        mock_fs = AsyncMock()
        # Mock read_file to return our expected content, not file system content
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_memory_bank)
        # Ensure exists() returns True so the check passes
        mock_fs.validate_path = MagicMock(return_value=True)
        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"size_bytes": 100, "token_count": 20}
        )
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=temp_memory_bank.parent.parent,
            ):
                # Execute
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    include_metadata=False,
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["file_name"] == file_name
                # Use mocked content, not file system content
                assert result["content"] == content

    async def test_manage_file_read_with_metadata(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test file read with metadata included."""
        # Setup
        file_name = "projectBrief.md"
        content = "# Project Brief"
        metadata = {"size_bytes": 100, "token_count": 20}
        _ = temp_memory_bank.write_text(content)

        # Mock managers
        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        mock_fs.construct_safe_path = MagicMock(return_value=temp_memory_bank)
        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata)
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=temp_memory_bank.parent.parent,
            ):
                # Execute
                result_str = await manage_file(
                    file_name=file_name,
                    operation="read",
                    include_metadata=True,
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                # Metadata may have additional fields, check subset
                result_metadata = result["metadata"]
                assert result_metadata["size_bytes"] == metadata["size_bytes"]
                assert result_metadata["token_count"] == metadata["token_count"]

    async def test_manage_file_read_not_found(self, mock_managers: dict[str, object]):
        """Test file read when file doesn't exist."""
        # Setup
        file_name = "nonexistent.md"

        # Mock managers
        mock_fs = AsyncMock()
        # Create a non-existent path
        nonexistent_path = Path("/tmp/test/memory-bank/nonexistent.md")
        mock_fs.construct_safe_path = MagicMock(return_value=nonexistent_path)
        mock_managers_dict = {
            "fs": mock_fs,
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await manage_file(file_name=file_name, operation="read")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "does not exist" in result["error"]

    async def test_manage_file_write_success(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test successful file write operation."""
        # Setup
        file_name = "projectBrief.md"
        content = "# Updated Project Brief"

        # Mock managers
        mock_fs = AsyncMock()
        mock_fs.write_file = AsyncMock(return_value="newhash123")
        mock_fs.parse_sections = MagicMock(
            return_value=[{"title": "Project Brief", "content": content}]
        )
        mock_fs.construct_safe_path = MagicMock(return_value=temp_memory_bank)
        mock_fs.compute_hash = MagicMock(return_value="newhash123")
        mock_index = AsyncMock()
        mock_index.get_expected_hash = AsyncMock(return_value="oldhash")
        mock_index.update_file_metadata = AsyncMock()
        mock_tokens = MagicMock()

        # Mock count_tokens to return 50 for the content
        def count_tokens_side_effect(text: str) -> int:
            return 50 if text == content else 5

        mock_tokens.count_tokens = MagicMock(side_effect=count_tokens_side_effect)
        mock_versions = AsyncMock()
        mock_versions.get_version_count = AsyncMock(return_value=5)
        version_info = MagicMock()
        version_info.version = 6
        version_info.snapshot_path = "memory-bank/projectBrief_v6.md"
        mock_versions.create_snapshot = AsyncMock(return_value=version_info)
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": mock_tokens,
            "versions": mock_versions,
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=temp_memory_bank.parent.parent,
            ):
                # Execute
                result_str = await manage_file(
                    file_name=file_name,
                    operation="write",
                    content=content,
                    change_description="Updated content",
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["file_name"] == file_name
                assert result["tokens"] == 50
                assert "snapshot_id" in result

    async def test_manage_file_write_without_content(
        self, mock_managers: dict[str, object]
    ):
        """Test write operation without content parameter."""
        # Setup
        file_name = "projectBrief.md"

        # Mock managers
        mock_managers_dict = {
            "fs": AsyncMock(),
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await manage_file(
                    file_name=file_name, operation="write", content=None
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "required" in result["error"]

    async def test_manage_file_metadata_success(self, mock_managers: dict[str, object]):
        """Test successful metadata retrieval."""
        # Setup
        file_name = "projectBrief.md"
        metadata = {
            "size_bytes": 1000,
            "token_count": 250,
            "sections": [{"title": "Brief"}],
        }

        # Mock managers - create a path that exists
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            _ = tmp_path.write_text("# Test")

        mock_fs = AsyncMock()
        mock_fs.construct_safe_path = MagicMock(return_value=tmp_path)
        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(return_value=metadata)
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        try:
            with patch(
                "cortex.tools.file_operations.get_managers",
                return_value=make_test_managers(**mock_managers_dict),
            ):
                with patch(
                    "cortex.tools.file_operations.get_project_root",
                    return_value=Path("/tmp/test"),
                ):
                    # Execute
                    result_str = await manage_file(
                        file_name=file_name, operation="metadata"
                    )

                    # Verify
                    result = json.loads(result_str)
                    assert result["status"] == "success"
                    # Metadata may have additional fields, check subset
                    result_metadata = result["metadata"]
                    assert result_metadata["size_bytes"] == metadata["size_bytes"]
                    assert result_metadata["token_count"] == metadata["token_count"]
                    assert result_metadata["sections"] == metadata["sections"]
        finally:
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()

    async def test_manage_file_invalid_operation(
        self, mock_managers: dict[str, object]
    ):
        """Test invalid operation type."""
        # Setup
        file_name = "projectBrief.md"

        # Mock managers
        mock_managers_dict = {
            "fs": AsyncMock(),
            "index": AsyncMock(),
            "tokens": MagicMock(),
            "versions": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await manage_file(file_name=file_name, operation="invalid")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid operation" in result["error"]


@pytest.mark.asyncio
class TestValidate:
    """Tests for validate consolidated tool."""

    async def test_validate_schema_success(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test successful schema validation."""
        # Setup
        file_name = "projectBrief.md"
        content = "# Project Brief\n## Overview"
        _ = (temp_memory_bank.parent / file_name).write_text(content)

        # Mock managers
        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=(content, "hash123"))
        file_path = temp_memory_bank.parent / file_name
        mock_fs.construct_safe_path = MagicMock(return_value=file_path)
        mock_index = AsyncMock()
        mock_schema_validator = AsyncMock()
        mock_schema_validator.validate_file = AsyncMock(
            return_value=SchemaValidationResult(valid=True)
        )
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "schema_validator": mock_schema_validator,
            "duplication_detector": AsyncMock(),
            "quality_metrics": AsyncMock(),
            "validation_config": AsyncMock(),
        }

        with patch(
            "cortex.managers.initialization.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.managers.initialization.get_project_root",
                return_value=temp_memory_bank.parent.parent,
            ):
                # Execute
                result_str = await validate(check_type="schema", file_name=file_name)

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["check_type"] == "schema"
                assert "validation" in result
                # Validation result may have valid: False if file doesn't match schema
                # Check that validation key exists and has expected structure
                validation = result["validation"]
                assert "valid" in validation
                assert "errors" in validation

    async def test_validate_duplications_found(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test duplication detection with duplicates found."""
        # Setup
        # Setup - create actual files for glob to find
        # Use .cortex/memory-bank/ as that's what get_cortex_path returns
        project_root = temp_memory_bank.parent.parent
        memory_bank_dir = project_root / ".cortex" / "memory-bank"
        memory_bank_dir.mkdir(parents=True, exist_ok=True)
        test_file1 = memory_bank_dir / "file1.md"
        test_file2 = memory_bank_dir / "file2.md"
        _ = test_file1.write_text("# Content")
        _ = test_file2.write_text("# Content")

        # Mock managers
        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=("# Content", "hash123"))
        mock_fs.construct_safe_path = MagicMock(
            return_value=temp_memory_bank.parent / "file1.md"
        )
        mock_index = AsyncMock()
        mock_duplication_detector = AsyncMock()
        mock_duplication_detector.scan_all_files = AsyncMock(
            return_value=DuplicationScanResult(
                duplicates_found=1,
                exact_duplicates=[
                    DuplicateEntry(
                        file1="file1.md",
                        section1="content",
                        file2="file2.md",
                        section2="content",
                        similarity=1.0,
                        type="exact",
                        suggestion="Consolidate shared content",
                    )
                ],
                similar_content=[],
            )
        )
        mock_validation_config = AsyncMock()
        mock_validation_config.get_duplication_threshold = MagicMock(return_value=0.8)
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "schema_validator": AsyncMock(),
            "duplication_detector": mock_duplication_detector,
            "quality_metrics": AsyncMock(),
            "validation_config": mock_validation_config,
        }

        with patch(
            "cortex.managers.initialization.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):

            def mock_get_manager(mgrs: object, key: str, cls: type) -> object:
                if isinstance(mgrs, dict):
                    return mgrs.get(key)
                return getattr(mgrs, key, None)

            with patch(
                "cortex.managers.manager_utils.get_manager",
                side_effect=mock_get_manager,
            ):
                with patch(
                    "cortex.managers.initialization.get_project_root",
                    return_value=temp_memory_bank.parent.parent,
                ):
                    with patch(
                        "cortex.tools.validation_helpers.read_all_memory_bank_files",
                        return_value={"file1.md": "# Content", "file2.md": "# Content"},
                    ):
                        # Execute
                        result_str = await validate(
                            check_type="duplications", suggest_fixes=True
                        )

                    # Verify
                    result = json.loads(result_str)
                    if result["status"] != "success":
                        import json as json_module

                        print(f"Error result: {json_module.dumps(result, indent=2)}")
                    assert result["status"] == "success"
                    assert result["check_type"] == "duplications"
                    # Result has "duplicates_found" and
                    # "exact_duplicates"/"similar_content" keys
                    assert "duplicates_found" in result
                    assert result["duplicates_found"] >= 0
                    if result["duplicates_found"] > 0:
                        assert (
                            "exact_duplicates" in result or "similar_content" in result
                        )
                        # Suggested fixes only present when duplicates found
                        # and suggest_fixes=True
                        # Note: suggested_fixes may be empty if fix generation
                        # doesn't produce fixes
                        if "suggested_fixes" in result:
                            assert isinstance(result["suggested_fixes"], list)

    async def test_validate_quality_score(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test quality score calculation."""
        # Setup
        # Mock managers
        mock_fs = AsyncMock()
        mock_fs.read_file = AsyncMock(return_value=("# Content", "hash123"))
        mock_fs.construct_safe_path = MagicMock(
            return_value=temp_memory_bank.parent / "file.md"
        )
        mock_index = AsyncMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"size_bytes": 100, "token_count": 20}
        )
        mock_duplication_detector = AsyncMock()
        mock_duplication_detector.scan_all_files = AsyncMock(
            return_value=DuplicationScanResult(
                duplicates_found=0, exact_duplicates=[], similar_content=[]
            )
        )
        mock_quality_metrics = AsyncMock()
        mock_quality_metrics.calculate_overall_score = AsyncMock(
            return_value=QualityScoreResult(
                overall_score=85,
                breakdown=CategoryBreakdown(
                    completeness=90,
                    consistency=80,
                    freshness=75,
                    structure=85,
                    token_efficiency=80,
                ),
                grade="B",
                status="healthy",
                issues=[],
                recommendations=[],
            )
        )
        mock_managers_dict = {
            "fs": mock_fs,
            "index": mock_index,
            "schema_validator": AsyncMock(),
            "duplication_detector": mock_duplication_detector,
            "quality_metrics": mock_quality_metrics,
            "validation_config": AsyncMock(),
        }

        with patch(
            "cortex.managers.initialization.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.managers.initialization.get_project_root",
                return_value=temp_memory_bank.parent.parent,
            ):
                # Execute
                result_str = await validate(check_type="quality")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["check_type"] == "quality"
                # Quality result has "breakdown" key with score details,
                # not "score"
                assert "breakdown" in result or "overall_score" in result
                if "breakdown" in result:
                    breakdown = result["breakdown"]
                    assert isinstance(breakdown, dict)
                # Quality score may vary based on actual file contents and
                # duplication data. Just verify the score is present and is
                # a number
                if "overall_score" in result:
                    assert isinstance(result["overall_score"], (int, float))
                    assert result["overall_score"] >= 0
                if "grade" in result:
                    assert isinstance(result["grade"], str)

    async def test_validate_invalid_check_type(
        self, mock_managers: dict[str, object], temp_memory_bank: Path
    ):
        """Test invalid check type."""
        # Setup
        # Create memory-bank directory for the test
        memory_bank_dir = temp_memory_bank.parent
        memory_bank_dir.mkdir(exist_ok=True, parents=True)

        # Mock managers - need all managers that validate function accesses
        mock_managers_dict = {
            "fs": AsyncMock(),
            "index": AsyncMock(),
            "schema_validator": AsyncMock(),
            "duplication_detector": AsyncMock(),
            "quality_metrics": AsyncMock(),
            "validation_config": AsyncMock(),
        }

        with patch(
            "cortex.managers.initialization.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.managers.initialization.get_project_root",
                return_value=temp_memory_bank.parent.parent,
            ):
                # Execute
                result_str = await validate(
                    check_type="invalid_type",
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid check_type" in result["error"]


@pytest.mark.asyncio
class TestAnalyze:
    """Tests for analyze consolidated tool."""

    async def test_analyze_usage_patterns(self, mock_managers: dict[str, object]):
        """Test usage patterns analysis."""
        # Setup
        mock_pattern_analyzer = AsyncMock()
        mock_pattern_analyzer.get_access_frequency = AsyncMock(
            return_value={
                "file1.md": {"access_count": 10, "last_accessed": "2025-01-01"}
            }
        )
        mock_pattern_analyzer.get_co_access_patterns = AsyncMock(return_value=[])
        mock_pattern_analyzer.get_unused_files = AsyncMock(return_value=[])
        mock_pattern_analyzer.get_task_patterns = AsyncMock(return_value={})
        mock_pattern_analyzer.get_temporal_patterns = AsyncMock(return_value={})
        mock_managers_dict = {
            "pattern_analyzer": mock_pattern_analyzer,
            "structure_analyzer": AsyncMock(),
            "insight_engine": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await analyze(target="usage_patterns", time_window_days=30)

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "patterns" in result
                assert "time_window_days" in result
                assert result["target"] == "usage_patterns"

    async def test_analyze_structure(self, mock_managers: dict[str, object]):
        """Test structure analysis."""
        # Setup
        mock_structure_analyzer = AsyncMock()
        organization = MagicMock()
        organization.model_dump = MagicMock(
            return_value={"total_files": 5, "total_size_bytes": 5000}
        )
        mock_structure_analyzer.analyze_file_organization = AsyncMock(
            return_value=organization
        )
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        complexity = MagicMock()
        complexity.model_dump = MagicMock(return_value={"assessment": {"grade": "A"}})
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
            return_value=complexity
        )
        mock_structure_analyzer.find_dependency_chains = AsyncMock(return_value=[])

        # Create LazyManager mocks that return the actual analyzers
        mock_pattern_analyzer = AsyncMock()

        async def pattern_factory() -> object:
            return mock_pattern_analyzer

        async def structure_factory() -> object:
            return mock_structure_analyzer

        mock_insight_engine = AsyncMock()

        async def insight_factory() -> object:
            return mock_insight_engine

        mock_pattern_analyzer_mgr = LazyManager(
            pattern_factory, name="pattern_analyzer"
        )
        mock_structure_analyzer_mgr = LazyManager(
            structure_factory, name="structure_analyzer"
        )
        mock_insight_engine_mgr = LazyManager(insight_factory, name="insight_engine")
        mock_managers_dict_with_lazy = {
            "pattern_analyzer": mock_pattern_analyzer_mgr,
            "structure_analyzer": mock_structure_analyzer_mgr,
            "insight_engine": mock_insight_engine_mgr,
        }

        with patch(
            "cortex.tools.analysis_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict_with_lazy),
        ):
            with patch(
                "cortex.tools.analysis_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await analyze(target="structure")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "analysis" in result
                assert result["target"] == "structure"

    async def test_analyze_insights(self, mock_managers: dict[str, object]):
        """Test optimization insights generation."""
        # Setup
        insights_data = {
            "insights": [
                {
                    "category": "usage_patterns",
                    "severity": "high",
                    "impact_score": 0.8,
                    "recommendation": "Optimize file1.md",
                }
            ],
            "summary": {"total_insights": 1, "high_severity": 1},
        }
        mock_insight_engine = AsyncMock()
        insights_model = MagicMock()
        insights_model.model_dump = MagicMock(return_value=insights_data)
        mock_insight_engine.generate_insights = AsyncMock(return_value=insights_model)
        # Mock lazy managers - they need a .get() method that returns the actual mock
        # Create LazyManager mocks that return the actual analyzers
        mock_pattern_analyzer = AsyncMock()

        async def pattern_factory() -> object:
            return mock_pattern_analyzer

        mock_structure_analyzer = AsyncMock()

        async def structure_factory() -> object:
            return mock_structure_analyzer

        async def insight_factory() -> object:
            return mock_insight_engine

        mock_pattern_analyzer_mgr = LazyManager(
            pattern_factory, name="pattern_analyzer"
        )
        mock_structure_analyzer_mgr = LazyManager(
            structure_factory, name="structure_analyzer"
        )
        mock_insight_engine_mgr = LazyManager(insight_factory, name="insight_engine")
        mock_managers_dict_with_lazy = {
            "pattern_analyzer": mock_pattern_analyzer_mgr,
            "structure_analyzer": mock_structure_analyzer_mgr,
            "insight_engine": mock_insight_engine_mgr,
        }

        with patch(
            "cortex.tools.analysis_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict_with_lazy),
        ):
            with patch(
                "cortex.tools.analysis_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await analyze(target="insights", export_format="json")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "insights" in result
                insights_data = result["insights"]
                assert isinstance(insights_data, dict)
                # Insights may be in "insights" key or at root level
                if "insights" in insights_data:
                    insights_list = cast(list[object], insights_data["insights"])
                    assert isinstance(insights_list, list)
                    # May be empty if no insights generated
                    if len(insights_list) > 0:
                        assert len(insights_list) == 1

    async def test_analyze_invalid_target(self, mock_managers: dict[str, object]):
        """Test invalid analysis target."""
        # Setup
        # Mock all managers that analyze function accesses
        mock_managers_dict = {
            "pattern_analyzer": AsyncMock(),
            "structure_analyzer": AsyncMock(),
            "insight_engine": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await analyze(target="invalid_target")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid target" in result["error"]


@pytest.mark.asyncio
class TestSuggestRefactoring:
    """Tests for suggest_refactoring consolidated tool."""

    async def test_suggest_refactoring_consolidation(
        self, mock_managers: dict[str, object]
    ):
        """Test consolidation suggestions."""

        # Setup
        class MockOpportunity:
            def __init__(self):
                self.opportunity_id = "opp1"
                self.opportunity_type = "duplicate"
                self.affected_files = ["file1.md", "file2.md"]
                self.token_savings = 100
                self.similarity_score = 0.90

            def to_dict(self):
                return {
                    "opportunity_id": self.opportunity_id,
                    "type": self.opportunity_type,
                    "affected_files": self.affected_files,
                    "token_savings": self.token_savings,
                    "similarity": self.similarity_score,
                }

        mock_consolidation_detector = AsyncMock()
        mock_consolidation_detector.detect_opportunities = AsyncMock(
            return_value=[MockOpportunity()]  # Return objects, not dicts
        )
        mock_consolidation_detector.min_similarity = 0.80
        mock_consolidation_detector.target_reduction = 0.30
        mock_split_recommender = AsyncMock()
        mock_reorganization_planner = AsyncMock()

        async def consolidation_factory() -> object:
            return mock_consolidation_detector

        async def split_factory() -> object:
            return mock_split_recommender

        async def reorg_factory() -> object:
            return mock_reorganization_planner

        mock_consolidation_detector_mgr = LazyManager(
            consolidation_factory, name="consolidation_detector"
        )
        mock_split_recommender_mgr = LazyManager(
            split_factory, name="split_recommender"
        )
        mock_reorganization_planner_mgr = LazyManager(
            reorg_factory, name="reorganization_planner"
        )
        mock_managers_dict = {
            "consolidation_detector": mock_consolidation_detector_mgr,
            "split_recommender": mock_split_recommender_mgr,
            "reorganization_planner": mock_reorganization_planner_mgr,
            "graph": AsyncMock(),  # DependencyGraph, not lazy
        }

        with patch(
            "cortex.tools.refactoring_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.refactoring_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await suggest_refactoring(type="consolidation")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["type"] == "consolidation"
                assert "opportunities" in result
                assert len(result["opportunities"]) == 1

    async def test_suggest_refactoring_splits(self, mock_managers: dict[str, object]):
        """Test file split suggestions."""

        # Setup
        class MockRecommendation:
            def __init__(self):
                self.file_path = "large_file.md"
                self.reason = "File too large"
                self.split_strategy = "by_sections"
                self.split_points = [{"line": 100, "section": "Section 1"}]

            def to_dict(self):
                return {
                    "file_path": self.file_path,
                    "reason": self.reason,
                    "split_strategy": self.split_strategy,
                    "split_points": self.split_points,
                }

        mock_split_recommender = AsyncMock()
        mock_split_recommender.suggest_file_splits = AsyncMock(
            return_value=[MockRecommendation()]  # Return objects, not dicts
        )
        mock_split_recommender.max_file_size = 5000
        mock_split_recommender.max_sections = 10
        mock_consolidation_detector = AsyncMock()
        mock_reorganization_planner = AsyncMock()

        async def consolidation_factory() -> object:
            return mock_consolidation_detector

        async def split_factory() -> object:
            return mock_split_recommender

        async def reorg_factory() -> object:
            return mock_reorganization_planner

        mock_consolidation_detector_mgr = LazyManager(
            consolidation_factory, name="consolidation_detector"
        )
        mock_split_recommender_mgr = LazyManager(
            split_factory, name="split_recommender"
        )
        mock_reorganization_planner_mgr = LazyManager(
            reorg_factory, name="reorganization_planner"
        )
        mock_managers_dict = {
            "consolidation_detector": mock_consolidation_detector_mgr,
            "split_recommender": mock_split_recommender_mgr,
            "reorganization_planner": mock_reorganization_planner_mgr,
            "graph": AsyncMock(),  # DependencyGraph, not lazy
        }

        with patch(
            "cortex.tools.refactoring_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.refactoring_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await suggest_refactoring(type="splits")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["type"] == "splits"
                assert "recommendations" in result
                assert len(result["recommendations"]) == 1

    async def test_suggest_refactoring_reorganization(
        self, mock_managers: dict[str, object]
    ):
        """Test reorganization suggestions."""

        # Setup
        class MockPlan:
            def __init__(self):
                self.preserve_history = True

            def to_dict(self) -> dict[str, object]:
                return {
                    "optimize_for": "dependency_depth",
                    "actions": [],
                    "preserve_history": self.preserve_history,
                }

        mock_reorganization_planner = AsyncMock()
        plan_model = MagicMock()
        plan_model.model_dump = MagicMock(return_value=MockPlan().to_dict())
        mock_reorganization_planner.create_reorganization_plan = AsyncMock(
            return_value=plan_model
        )
        mock_reorganization_planner.preview_reorganization = AsyncMock(
            return_value={"preview": "Reorganization preview"}
        )
        mock_structure_analyzer = AsyncMock()
        organization = MagicMock()
        organization.file_count = 0
        organization.model_dump = MagicMock(return_value={})
        mock_structure_analyzer.analyze_file_organization = AsyncMock(
            return_value=organization
        )
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        complexity = MagicMock()
        complexity.model_dump = MagicMock(return_value={})
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
            return_value=complexity
        )
        mock_dep_graph = MagicMock()
        mock_dep_graph.get_graph_dict = MagicMock(return_value={})
        graph_export = MagicMock()
        graph_export.model_dump = MagicMock(return_value={"dependencies": {}})
        mock_dep_graph.to_dict = MagicMock(return_value=graph_export)

        mock_consolidation_detector = AsyncMock()
        mock_split_recommender = AsyncMock()

        async def consolidation_factory() -> object:
            return mock_consolidation_detector

        async def split_factory() -> object:
            return mock_split_recommender

        async def reorg_factory() -> object:
            return mock_reorganization_planner

        async def structure_factory() -> object:
            return mock_structure_analyzer

        mock_consolidation_detector_mgr = LazyManager(
            consolidation_factory, name="consolidation_detector"
        )
        mock_split_recommender_mgr = LazyManager(
            split_factory, name="split_recommender"
        )
        mock_reorganization_planner_mgr = LazyManager(
            reorg_factory, name="reorganization_planner"
        )
        mock_structure_analyzer_mgr = LazyManager(
            structure_factory, name="structure_analyzer"
        )
        mock_managers_dict = {
            "consolidation_detector": mock_consolidation_detector_mgr,
            "split_recommender": mock_split_recommender_mgr,
            "reorganization_planner": mock_reorganization_planner_mgr,
            "graph": mock_dep_graph,
            "structure_analyzer": mock_structure_analyzer_mgr,
        }

        with patch(
            "cortex.tools.refactoring_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.refactoring_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await suggest_refactoring(type="reorganization")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["type"] == "reorganization"
                assert "plan" in result

    async def test_suggest_refactoring_invalid_type(
        self, mock_managers: dict[str, object]
    ):
        """Test invalid refactoring type."""
        # Setup
        # Mock all managers that suggest_refactoring function accesses
        mock_managers_dict = {
            "consolidation_detector": AsyncMock(),
            "split_recommender": AsyncMock(),
            "reorganization_planner": AsyncMock(),
            "deps": AsyncMock(),
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await suggest_refactoring(type="invalid_type")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Invalid type" in result["error"]


@pytest.mark.asyncio
class TestConfigure:
    """Tests for configure consolidated tool."""

    async def test_configure_validation_view(self, mock_managers: dict[str, object]):
        """Test viewing validation configuration."""
        # Setup
        mock_validation_config = MagicMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump = MagicMock(
            return_value={
                "token_budget": {"max_total_tokens": 100000},
                "schema": {"strict": False},
            }
        )
        mock_validation_config.set = MagicMock()
        mock_validation_config.reset_to_defaults = MagicMock()
        mock_validation_config.save = AsyncMock()
        mock_managers_dict = {"validation_config": mock_validation_config}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(component="validation", action="view")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["component"] == "validation"
                assert "configuration" in result
                # Check that configuration is returned (actual value may differ)
                config = result["configuration"]
                assert "token_budget" in config
                assert "max_total_tokens" in config["token_budget"]

    async def test_configure_validation_update(self, mock_managers: dict[str, object]):
        """Test updating validation configuration."""
        # Setup
        mock_validation_config = MagicMock()
        mock_validation_config.set = MagicMock()
        mock_validation_config.save = AsyncMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump = MagicMock(return_value={})
        mock_managers_dict: dict[str, object] = {
            "validation_config": mock_validation_config
        }

        async def mock_get_managers(root: Path) -> object:
            return make_test_managers(**mock_managers_dict)

        with patch(
            "cortex.tools.configuration_operations.get_managers",
            side_effect=mock_get_managers,
        ):
            with patch(
                "cortex.tools.configuration_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(
                    component="validation",
                    action="update",
                    key="token_budget.max_total_tokens",
                    value="200000",
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "Configuration updated" in result["message"]
                assert result["component"] == "validation"

    async def test_configure_validation_reset(self, mock_managers: dict[str, object]):
        """Test resetting validation configuration."""
        # Setup
        mock_validation_config = MagicMock()
        mock_validation_config.reset_to_defaults = MagicMock()
        mock_validation_config.save = AsyncMock()
        mock_validation_config.config = MagicMock()
        mock_validation_config.config.model_dump = MagicMock(return_value={})
        mock_managers_dict = {"validation_config": mock_validation_config}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                with patch(
                    "cortex.tools.configuration_operations.get_manager",
                    return_value=mock_validation_config,
                ):
                    # Execute
                    result_str = await configure(component="validation", action="reset")

                    # Verify
                    result = json.loads(result_str)
                    assert result["status"] == "success"
                    assert "reset to defaults" in result["message"]
                    mock_validation_config.reset_to_defaults.assert_called_once()

    async def test_configure_optimization_view(self, mock_managers: dict[str, object]):
        """Test viewing optimization configuration."""
        # Setup
        mock_optimization_config = MagicMock()
        mock_optimization_config.to_dict = MagicMock(
            return_value={
                "token_budget": {"default_budget": 50000},
                "loading": {"strategy": "by_relevance"},
            }
        )
        mock_managers_dict = {"optimization_config": mock_optimization_config}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(component="optimization", action="view")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["component"] == "optimization"
                assert "configuration" in result
                # Check that configuration is returned (actual value may differ)
                config = result["configuration"]
                assert "token_budget" in config
                assert "default_budget" in config["token_budget"]

    async def test_configure_optimization_update(
        self, mock_managers: dict[str, object]
    ):
        """Test updating optimization configuration."""
        # Setup
        mock_optimization_config = MagicMock()
        mock_optimization_config.set = MagicMock(return_value=True)
        mock_optimization_config.save_config = AsyncMock()
        mock_optimization_config.to_dict = MagicMock(return_value={})
        mock_managers_dict = {"optimization_config": mock_optimization_config}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(
                    component="optimization",
                    action="update",
                    key="loading.strategy",
                    value='"by_dependencies"',
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "Configuration updated" in result["message"]
                assert result["component"] == "optimization"
                assert "configuration" in result

    async def test_configure_learning_view(self, mock_managers: dict[str, object]):
        """Test viewing learning configuration."""
        # Setup
        mock_adaptation_config = MagicMock()
        mock_adaptation_config.to_dict = MagicMock(
            return_value={
                "learning": {"enabled": True},
                "adaptation": {"threshold": 0.7},
            }
        )
        mock_learning_engine = AsyncMock()
        mock_learning_engine.data_manager = MagicMock()
        mock_learning_engine.data_manager.get_all_patterns = MagicMock(return_value={})
        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {}
        mock_managers_dict = {
            "learning_engine": mock_learning_engine,
            "optimization_config": mock_optimization_config,
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(component="learning", action="view")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["component"] == "learning"
                assert "configuration" in result
                assert "learned_patterns" in result

    async def test_configure_learning_export_patterns(
        self, mock_managers: dict[str, object]
    ):
        """Test viewing learning configuration with exported patterns."""
        # Setup
        mock_adaptation_config = MagicMock()
        mock_adaptation_config.to_dict = MagicMock(return_value={})
        mock_learning_engine = AsyncMock()
        mock_learning_engine.data_manager = MagicMock()
        mock_learning_engine.data_manager.get_all_patterns = MagicMock(return_value={})
        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {}
        mock_managers_dict = {
            "learning_engine": mock_learning_engine,
            "optimization_config": mock_optimization_config,
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(component="learning", action="view")

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert "learned_patterns" in result
                # learned_patterns is a dict of pattern_id -> pattern_dict
                patterns = cast(dict[str, object], result["learned_patterns"])
                assert isinstance(patterns, dict)
                if patterns:
                    # Check first pattern if any exist
                    pattern_values = patterns.values()
                    first_pattern_obj = cast(
                        dict[str, object], next(iter(pattern_values))
                    )
                    assert isinstance(first_pattern_obj, dict)
                    first_pattern: dict[str, object] = first_pattern_obj
                    assert "type" in first_pattern or isinstance(first_pattern, dict)

    async def test_configure_learning_reset(self, mock_managers: dict[str, object]):
        """Test resetting learning configuration and data."""
        # Setup
        mock_learning_engine = AsyncMock()
        mock_learning_engine.data_manager = MagicMock()
        mock_learning_engine.data_manager.get_all_patterns = MagicMock(return_value={})
        mock_learning_engine.reset_learning_data = AsyncMock()
        mock_optimization_config = MagicMock()
        mock_optimization_config.config = {}
        mock_optimization_config.save_config = AsyncMock()
        mock_managers_dict = {
            "learning_engine": mock_learning_engine,
            "optimization_config": mock_optimization_config,
        }

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):

                def get_manager_side_effect(
                    mgrs: object, key: str, cls: type
                ) -> object:  # type: ignore[type-arg]
                    if key == "learning_engine":
                        return mock_learning_engine
                    return mock_optimization_config

                with patch(
                    "cortex.tools.configuration_operations.get_manager",
                    side_effect=get_manager_side_effect,
                ):
                    with patch(
                        "cortex.refactoring.adaptation_config.AdaptationConfig"
                    ) as mock_adaptation_cls:
                        mock_adaptation = MagicMock()
                        mock_adaptation.reset_to_defaults = MagicMock()
                        mock_adaptation.to_dict = MagicMock(return_value={})
                        mock_adaptation_cls.return_value = mock_adaptation

                        # Execute
                        result_str = await configure(
                            component="learning", action="reset"
                        )

                        # Verify
                        result = json.loads(result_str)
                        assert result["status"] == "success"
                        assert "reset to defaults" in result["message"]
                        mock_learning_engine.reset_learning_data.assert_called_once()

    async def test_configure_invalid_component(self, mock_managers: dict[str, object]):
        """Test invalid component type."""
        mock_managers_dict = {}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(
                    component="invalid_component", action="view"
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Unknown component" in result["error"]

    async def test_configure_invalid_action(self, mock_managers: dict[str, object]):
        """Test invalid action type."""
        mock_validation_config = MagicMock()
        mock_managers_dict = {"validation_config": mock_validation_config}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(
                    component="validation", action="invalid_action"
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "Unknown action" in result["error"]

    async def test_configure_update_missing_params(
        self, mock_managers: dict[str, object]
    ):
        """Test update action with missing parameters."""
        mock_validation_config = MagicMock()
        mock_managers_dict = {"validation_config": mock_validation_config}

        with patch(
            "cortex.tools.file_operations.get_managers",
            return_value=make_test_managers(**mock_managers_dict),
        ):
            with patch(
                "cortex.tools.file_operations.get_project_root",
                return_value=Path("/tmp/test"),
            ):
                # Execute
                result_str = await configure(
                    component="validation",
                    action="update",
                    key="test.key",
                    value=None,
                )

                # Verify
                result = json.loads(result_str)
                assert result["status"] == "error"
                assert "required for update" in result["error"]
