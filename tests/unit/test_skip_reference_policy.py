"""Unit tests for skip reference policy helpers."""

from __future__ import annotations

import pytest

from tests.skip_reference_policy import (
    collect_runtime_pytest_skip_violations_from_source,
    describe_skip_policy_violation,
    enforce_unconditional_skip_markers,
    skip_reason_has_tracked_reference,
)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("ref: cleanup-skipped-legacy-tests", True),
        ("REF: my-plan-slug", True),
        ("issue: 123", True),
        ("issue: #456", True),
        ("see plan: cleanup-skipped-legacy-tests", True),
        ("see cleanup-skipped-legacy-tests", True),
        ("missing files — see cleanup-skipped-legacy-tests", True),
        ("", False),
        ("no reference here", False),
        ("see", False),
    ],
)
def test_skip_reason_has_tracked_reference(reason: str, expected: bool) -> None:
    assert skip_reason_has_tracked_reference(reason) is expected


def test_describe_skip_policy_violation_empty_reason() -> None:
    msg = describe_skip_policy_violation("t.py::test_x", None)
    assert "t.py::test_x" in msg
    assert "ref:" in msg


class _FakeMarker:
    def __init__(self, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        self.args = args
        self.kwargs = kwargs


class _FakeItem:
    def __init__(self, nodeid: str, marker: _FakeMarker | None) -> None:
        self.nodeid = nodeid
        self._skip = marker

    def get_closest_marker(self, name: str) -> _FakeMarker | None:
        if name == "skip":
            return self._skip
        return None


def test_enforce_skips_accepts_valid_marker() -> None:
    marker = _FakeMarker(
        (), {"reason": "optional file (ref: cleanup-skipped-legacy-tests)"}
    )
    item = _FakeItem("f.py::test_a", marker)
    enforce_unconditional_skip_markers([item])  # type: ignore[list-item]


def test_enforce_skips_accepts_reason_in_args() -> None:
    marker = _FakeMarker(("ref: cleanup-skipped-legacy-tests",), {})
    item = _FakeItem("f.py::test_b", marker)
    enforce_unconditional_skip_markers([item])  # type: ignore[list-item]


def test_enforce_skips_rejects_missing_ref() -> None:
    marker = _FakeMarker((), {"reason": "missing optional resource"})
    item = _FakeItem("f.py::test_c", marker)
    with pytest.raises(pytest.UsageError, match="ref:"):
        enforce_unconditional_skip_markers([item])  # type: ignore[list-item]


def test_ast_scan_accepts_literal_reason_with_ref() -> None:
    src = 'import pytest\npytest.skip("hold (ref: cleanup-skipped-legacy-tests)")\n'
    assert not collect_runtime_pytest_skip_violations_from_source(src, rel_path="t.py")


def test_ast_scan_accepts_fstring_with_ref_in_literal_segment() -> None:
    src = (
        "import pytest\n"
        'pytest.skip(f"not found {x!s} (ref: cleanup-skipped-legacy-tests)")\n'
    )
    assert not collect_runtime_pytest_skip_violations_from_source(src, rel_path="t.py")


def test_ast_scan_rejects_bare_skip() -> None:
    src = "import pytest\npytest.skip()\n"
    v = collect_runtime_pytest_skip_violations_from_source(src, rel_path="t.py")
    assert v and "requires a reason" in v[0][1]


def test_ast_scan_rejects_skip_without_ref() -> None:
    src = 'import pytest\npytest.skip("later")\n'
    v = collect_runtime_pytest_skip_violations_from_source(src, rel_path="t.py")
    assert v and "must include" in v[0][1]


def test_ast_scan_rejects_non_literal_reason() -> None:
    src = "import pytest\nmsg = 'x'\npytest.skip(msg)\n"
    v = collect_runtime_pytest_skip_violations_from_source(src, rel_path="t.py")
    assert v and "literal" in v[0][1]


def test_ast_scan_from_import_skip_alias() -> None:
    src = 'from pytest import skip\nskip("nope")\n'
    v = collect_runtime_pytest_skip_violations_from_source(src, rel_path="t.py")
    assert v
