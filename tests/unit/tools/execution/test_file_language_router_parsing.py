"""Unit tests for _parse_file_size_violations() and _parse_function_length_violations()."""

from __future__ import annotations

from pathlib import Path

from cortex.tools.execution import file_language_router as flr

# ---------------------------------------------------------------------------
# _parse_file_size_violations()
# ---------------------------------------------------------------------------


def test_parse_file_size_violations_python_format(tmp_path: Path) -> None:
    output = (
        "File size violations detected:\n\n"
        "  src/cortex/foo.py: 450 lines (max: 400, excess: 50)\n"
    )
    result = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert len(result) == 1
    assert result[0].lines == 450
    assert result[0].max_lines == 400
    assert result[0].excess == 50


def test_parse_file_size_violations_swift_format(tmp_path: Path) -> None:
    output = "  Sources/Foo/Bar.swift: 450 lines (max: 400, excess: 50)\n"
    result = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert len(result) == 1
    assert result[0].file.endswith("Bar.swift")
    assert result[0].lines == 450


def test_parse_file_size_violations_no_violations(tmp_path: Path) -> None:
    output = "All files within size limits (400 lines)\n"
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert violations == []


def test_parse_file_size_violations_multiple(tmp_path: Path) -> None:
    output = (
        "  src/a.py: 500 lines (max: 400, excess: 100)\n"
        "  src/b.py: 450 lines (max: 400, excess: 50)\n"
    )
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert len(violations) == 2


def test_parse_file_size_violations_ignores_unrecognised_lines(
    tmp_path: Path,
) -> None:
    output = "some unexpected line\nTotal violations: 0 file(s) exceed 400 lines\n"
    violations = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    assert violations == []


def test_parse_file_size_violations_excess_consistent(tmp_path: Path) -> None:
    output = "  src/foo.py: 450 lines (max: 400, excess: 50)\n"
    result = flr._parse_file_size_violations(  # pyright: ignore[reportPrivateUsage]
        output, tmp_path
    )
    v = result[0]
    assert v.excess == v.lines - v.max_lines


# ---------------------------------------------------------------------------
# _parse_function_length_violations()
# ---------------------------------------------------------------------------


def test_parse_function_length_violations_python_format(tmp_path: Path) -> None:
    output = (
        "  src/cortex/foo.py:\n"
        "    my_func() at line 42: 35 lines (max: 30, excess: 5)\n"
    )
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output,
            tmp_path,
            language="python",
        )
    )
    assert len(result) == 1
    v = result[0]
    assert v.function == "my_func"
    assert v.line == 42
    assert v.lines == 35
    assert v.max_lines == 30
    assert v.excess == 5


def test_parse_function_length_violations_swift_format(tmp_path: Path) -> None:
    output = "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)\n"
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="swift"
        )
    )
    assert len(result) == 1
    assert result[0].function == "myFunc"
    assert result[0].line == 42


def test_parse_function_length_violations_no_violations(tmp_path: Path) -> None:
    output = "All functions within length limits (30 lines)\n"
    violations = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="python"
        )
    )
    assert violations == []


def test_parse_function_length_violations_multiple_python(tmp_path: Path) -> None:
    output = (
        "  src/foo.py:\n"
        "    func_a() at line 10: 35 lines (max: 30, excess: 5)\n"
        "    func_b() at line 50: 40 lines (max: 30, excess: 10)\n"
    )
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="python"
        )
    )
    assert len(result) == 2
    assert {v.function for v in result} == {"func_a", "func_b"}


def test_parse_function_length_violations_multiple_swift(tmp_path: Path) -> None:
    output = (
        "  Sources/Foo.swift:10: funcA() — 35 lines (max: 30, excess: 5)\n"
        "  Sources/Foo.swift:50: funcB() — 40 lines (max: 30, excess: 10)\n"
    )
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="swift"
        )
    )
    assert len(result) == 2
    assert {v.function for v in result} == {"funcA", "funcB"}


def test_parse_function_length_violations_python_orphan_function_line_ignored(
    tmp_path: Path,
) -> None:
    # A function-violation line with no preceding file header is silently dropped.
    output = "    orphan_func() at line 10: 35 lines (max: 30, excess: 5)\n"
    result = (
        flr._parse_function_length_violations(  # pyright: ignore[reportPrivateUsage]
            output, tmp_path, language="python"
        )
    )
    assert result == []
