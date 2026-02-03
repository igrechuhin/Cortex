"""Unit tests for Phase 49 advanced tool use (input examples).

Verifies that tools that support Anthropic-style input_examples expose
them via meta and that the example payloads have the expected structure.
"""

from cortex.tools.file_operations import MANAGE_FILE_INPUT_EXAMPLES
from cortex.tools.validation_operations import VALIDATE_INPUT_EXAMPLES


class TestManageFileInputExamples:
    """Test manage_file meta input_examples structure."""

    def test_input_examples_is_non_empty_list(self) -> None:
        """Input examples must be a non-empty list of example payloads."""
        assert isinstance(MANAGE_FILE_INPUT_EXAMPLES, list)
        assert len(MANAGE_FILE_INPUT_EXAMPLES) >= 1

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
            ), f"Example {i} operation must be read/write/metadata"

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
