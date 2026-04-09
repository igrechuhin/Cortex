"""Unit tests for compression structural validation."""

from cortex.tools.compress.validate import validate_compressed


def _sample_original() -> str:
    return """# Title
## Details
- one
- two
1. three

Path: .cortex/synapse/prompts/plan.md and src/cortex/tools/compress/validate.py
URL: https://example.com/docs

```python
print("hello")
```
"""


def test_validate_compressed_success_case() -> None:
    # Arrange
    original = _sample_original()
    compressed = """# Title
## Details
- one
- two
1. three
Path: .cortex/synapse/prompts/plan.md src/cortex/tools/compress/validate.py
URL: https://example.com/docs
```python
print("hello")
```"""

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is True
    assert result.errors == []
    assert result.token_ratio < 1.0


def test_validate_compressed_reports_one_error() -> None:
    # Arrange
    original = _sample_original()
    compressed = """# Title
## Details
- one
- two
1. three
Path: .cortex/synapse/prompts/plan.md src/cortex/tools/compress/validate.py
```python
print("hello")
```"""

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is False
    assert result.errors == ["URL set mismatch."]


def test_validate_compressed_reports_many_errors() -> None:
    # Arrange
    original = _sample_original()
    compressed = """## Details
# Title
- one
path changed
https://different.example.dev
"""

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is False
    assert len(result.errors) >= 4
    assert "Heading count/order mismatch." in result.errors
    assert "Missing fenced code block from original content." in result.errors


def test_validate_compressed_requires_verbatim_code_block() -> None:
    # Arrange
    original = _sample_original()
    compressed = """# Title
## Details
- one
- two
1. three
Path: .cortex/synapse/prompts/plan.md src/cortex/tools/compress/validate.py
URL: https://example.com/docs
```python
print("HELLO")
```"""

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert "Missing fenced code block from original content." in result.errors


def test_validate_frontmatter_preserved() -> None:
    # Arrange
    original = "---\nname: plan\ntype: feature\n---\n# Title\nBody.\n"
    compressed = "---\nname: plan\ntype: feature\n---\n# Title\nBody.\n"

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert "YAML frontmatter missing from compressed output." not in result.errors
    assert "YAML frontmatter changed in compressed output." not in result.errors


def test_validate_frontmatter_missing() -> None:
    # Arrange
    original = "---\nname: plan\ntype: feature\n---\n# Title\nBody.\n"
    compressed = "# Title\nBody.\n"

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is False
    assert "YAML frontmatter missing from compressed output." in result.errors


def test_validate_frontmatter_changed() -> None:
    # Arrange
    original = "---\nname: plan\ntype: feature\n---\n# Title\nBody.\n"
    compressed = "---\nname: plan\ntype: bug\n---\n# Title\nBody.\n"

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is False
    assert "YAML frontmatter changed in compressed output." in result.errors


def test_validate_inline_code_preserved() -> None:
    # Arrange
    original = "Use `run_quality_gate()` and `autofix()` to validate.\n"
    compressed = "Use `run_quality_gate()` and `autofix()` to validate.\n"

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert not any("Inline code" in e for e in result.errors)


def test_validate_inline_code_missing() -> None:
    # Arrange
    original = "Use `run_quality_gate()` and `autofix()` to validate.\n"
    compressed = "Use run_quality_gate() and `autofix()` to validate.\n"

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is False
    assert any("Inline code span missing" in e for e in result.errors)


def test_validate_list_tolerance_tightened() -> None:
    # 9 items original, 8 compressed = ~11% loss — within old ±15% but outside new ±10%
    original_items = "\n".join(f"- item{i}" for i in range(9))
    compressed_items = "\n".join(f"- item{i}" for i in range(8))
    original = f"# T\n{original_items}\n"
    compressed = f"# T\n{compressed_items}\n"

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert result.is_valid is False
    assert "Bullet/numbered list item count outside +/-10% tolerance." in result.errors


def test_validate_compressed_checks_heading_order() -> None:
    # Arrange
    original = _sample_original()
    compressed = """## Details
# Title
- one
- two
1. three
Path: .cortex/synapse/prompts/plan.md src/cortex/tools/compress/validate.py
URL: https://example.com/docs
```python
print("hello")
```"""

    # Act
    result = validate_compressed(original, compressed)

    # Assert
    assert "Heading count/order mismatch." in result.errors
