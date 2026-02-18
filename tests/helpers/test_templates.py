"""Reusable test templates for common patterns.

Use these as copy-paste or reference when writing new tests to keep
AAA structure and coverage patterns consistent.
"""


def test_error_path_template() -> str:
    """Return a docstring/snippet template for testing error handling.

    Use for except blocks, validation failures, and invalid-input paths.
    """
    return '''
def test_<subject>_<error_condition>(self) -> None:
    """<Subject> raises <Error> when <condition>."""
    # Arrange: set up invalid input or condition
    invalid_input = ...

    # Act & Assert: expect specific exception
    with pytest.raises(ExpectedError) as exc_info:
        subject_under_test(invalid_input)

    assert "expected message fragment" in str(exc_info.value)
'''


def test_edge_case_template() -> str:
    """Return a docstring/snippet template for testing edge cases.

    Use for boundary values, empty input, None, min/max, empty collections.
    """
    return '''
def test_<subject>_<edge_description>(self) -> None:
    """<Subject> handles <edge case> correctly."""
    # Arrange: boundary or edge input
    edge_input = ...  # e.g. [], None, 0, "", max value

    # Act
    result = subject_under_test(edge_input)

    # Assert: expected behavior at boundary
    assert result == expected
'''


def test_validation_template() -> str:
    """Return a docstring/snippet template for testing validation logic.

    Use for schema validation, required fields, and format checks.
    """
    return '''
def test_<subject>_validates_<aspect>(self) -> None:
    """<Subject> validation rejects invalid <aspect>."""
    # Arrange: payload that fails validation
    invalid_payload = {"field": "invalid value"}

    # Act: run validation (or call that performs validation)
    result = validate_or_call(invalid_payload)

    # Assert: validation error or False
    assert result.valid is False
    assert any("field" in e for e in result.errors)
'''


def get_all_templates() -> dict[str, str]:
    """Return all template snippets keyed by name."""
    return {
        "error_path": test_error_path_template(),
        "edge_case": test_edge_case_template(),
        "validation": test_validation_template(),
    }
