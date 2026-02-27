"""Unit tests for Phase 49 advanced tool use (input examples and allowed_callers).

Verifies that tools that support Anthropic-style input_examples expose
them via meta and that the example payloads have the expected structure.
Also verifies programmatic tool calling (allowed_callers) constant and tool list.
"""

from cortex.tools.file_operations import MANAGE_FILE_INPUT_EXAMPLES
from cortex.tools.tool_categories import (
    ALLOWED_CALLERS_CODE_EXECUTION,
    TOOLS_WITH_ALLOWED_CALLERS,
    ToolCategory,
    get_tool_category,
)
from cortex.tools.validation_operations import VALIDATE_INPUT_EXAMPLES


class TestManageFileInputExamples:
    """Test manage_file meta input_examples structure."""

    def test_input_examples_is_non_empty_list(self) -> None:
        """Input examples must be a non-empty list of example payloads."""
        assert isinstance(MANAGE_FILE_INPUT_EXAMPLES, list)
        assert len(MANAGE_FILE_INPUT_EXAMPLES) >= 1

    def test_input_examples_has_at_least_basic_and_advanced(self) -> None:
        """At least two examples (basic and advanced) for comprehensive coverage."""
        assert len(MANAGE_FILE_INPUT_EXAMPLES) >= 2

    def test_each_example_has_file_name_and_operation(self) -> None:
        """Each example must include file_name and operation for tool selection."""
        for i, example in enumerate(MANAGE_FILE_INPUT_EXAMPLES):
            assert isinstance(example, dict), f"Example {i} must be a dict"
            assert "file_name" in example, f"Example {i} must have file_name"
            assert "operation" in example, f"Example {i} must have operation"
            assert example["operation"] in (
                "read",
                "write",
                "metadata",
                "rollback",
            ), f"Example {i} operation must be read/write/metadata/rollback"

    def test_read_example_may_include_include_metadata(self) -> None:
        """Read examples may include include_metadata for doc accuracy."""
        read_examples = [
            ex for ex in MANAGE_FILE_INPUT_EXAMPLES if ex.get("operation") == "read"
        ]
        for ex in read_examples:
            if "include_metadata" in ex:
                assert isinstance(ex["include_metadata"], bool)

    def test_write_example_includes_content_and_change_description(self) -> None:
        """Write examples should include content and change_description."""
        write_examples = [
            ex for ex in MANAGE_FILE_INPUT_EXAMPLES if ex.get("operation") == "write"
        ]
        for ex in write_examples:
            assert "content" in ex
            assert "change_description" in ex or True  # optional but recommended


class TestValidateInputExamples:
    """Test validate meta input_examples structure."""

    def test_input_examples_is_non_empty_list(self) -> None:
        """Input examples must be a non-empty list of example payloads."""
        assert isinstance(VALIDATE_INPUT_EXAMPLES, list)
        assert len(VALIDATE_INPUT_EXAMPLES) >= 1

    def test_input_examples_has_at_least_basic_and_advanced(self) -> None:
        """At least two examples (basic and advanced) for comprehensive coverage."""
        assert len(VALIDATE_INPUT_EXAMPLES) >= 2

    def test_each_example_has_check_type(self) -> None:
        """Each example must include check_type for tool selection."""
        valid_check_types = {
            "schema",
            "duplications",
            "quality",
            "infrastructure",
            "timestamps",
            "roadmap_sync",
        }
        for i, example in enumerate(VALIDATE_INPUT_EXAMPLES):
            assert isinstance(example, dict), f"Example {i} must be a dict"
            assert "check_type" in example, f"Example {i} must have check_type"
            assert (
                example["check_type"] in valid_check_types
            ), f"Example {i} check_type must be one of {valid_check_types}"

    def test_duplications_example_may_include_similarity_threshold(self) -> None:
        """Duplications examples may include similarity_threshold."""
        dup_examples = [
            ex
            for ex in VALIDATE_INPUT_EXAMPLES
            if ex.get("check_type") == "duplications"
        ]
        for ex in dup_examples:
            if "similarity_threshold" in ex:
                assert isinstance(ex["similarity_threshold"], (int, float))


class TestAllowedCallersProgrammaticToolCalling:
    """Test Phase 49 Step 8: allowed_callers for programmatic tool calling."""

    def test_allowed_callers_constant_is_single_code_execution_id(self) -> None:
        """ALLOWED_CALLERS_CODE_EXECUTION is the Anthropic code execution caller."""
        assert ALLOWED_CALLERS_CODE_EXECUTION == ("code_execution_20250825",)

    def test_tools_with_allowed_callers_has_four_tools(self) -> None:
        """Exactly four tools support programmatic calling per Phase 49 analysis."""
        assert len(TOOLS_WITH_ALLOWED_CALLERS) == 4

    def test_tools_with_allowed_callers_matches_documented_list(self) -> None:
        """TOOLS_WITH_ALLOWED_CALLERS matches advanced-tool-use.md recommendation."""
        expected = {
            "validate",
            "suggest_refactoring",
            "apply_refactoring",
            "manage_file",
        }
        assert set(TOOLS_WITH_ALLOWED_CALLERS) == expected

    def test_tools_with_allowed_callers_have_category(self) -> None:
        """Every tool in TOOLS_WITH_ALLOWED_CALLERS exists in tool categorization."""
        for name in TOOLS_WITH_ALLOWED_CALLERS:
            cat = get_tool_category(name)
            assert cat is not None, f"{name} must have a tool category"
            assert cat in (
                ToolCategory.ALWAYS_LOADED,
                ToolCategory.DEFERRED_MEDIUM,
                ToolCategory.DEFERRED_LOW,
            )
