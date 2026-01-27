from cortex.structure.template_validator import (
    validate_template_content,
    validate_template_variables,
)


def test_validate_template_content_when_empty_returns_false() -> None:
    # Arrange
    template = ""

    # Act
    result = validate_template_content(template)

    # Assert
    assert result is False


def test_validate_template_content_when_whitespace_only_returns_false() -> None:
    # Arrange
    template = "   \n\t  "

    # Act
    result = validate_template_content(template)

    # Assert
    assert result is False


def test_validate_template_content_when_non_empty_returns_true() -> None:
    # Arrange
    template = "# Title\n\nSome content"

    # Act
    result = validate_template_content(template)

    # Assert
    assert result is True


def test_validate_template_variables_when_missing_returns_false_and_missing_list() -> (
    None
):
    # Arrange
    template = "Hello {name}. Today is {date}."
    variables = {"name": "Ada"}

    # Act
    is_valid, missing = validate_template_variables(template, variables)

    # Assert
    assert is_valid is False
    assert "date" in missing


def test_validate_template_variables_when_all_provided_returns_true_and_empty_list() -> (  # noqa: E501
    None
):
    # Arrange
    template = "Hello {name}. Today is {date}."
    variables = {"name": "Ada", "date": "2026-01-25"}

    # Act
    is_valid, missing = validate_template_variables(template, variables)

    # Assert
    assert is_valid is True
    assert missing == []
