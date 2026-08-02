"""Regression tests for the Completed Work section matcher in plan completion."""

from cortex.tools.plans.completion_content import create_section_and_append

DATE = "2026-08-01"


def _entry_line(content: str) -> str:
    return next(line for line in content.split("\n") if line.startswith("- ✅"))


def test_undated_completed_work_heading_is_matched() -> None:
    """An undated '## Completed Work' heading must not abort the append."""
    content = "# Active Context\n\n## Completed Work\n\n- old entry\n"
    new_content, line = create_section_and_append(content, DATE, "My Plan", "done")
    assert line is not None
    assert f"## Completed Work ({DATE})" in new_content
    assert "**My Plan**" in _entry_line(new_content)
    assert new_content.split("\n")[line - 1] == _entry_line(new_content)
    assert "- old entry" in new_content


def test_dated_heading_still_matched() -> None:
    content = "# Active Context\n\n## Completed Work (2026-07-31)\n\n- old\n"
    new_content, line = create_section_and_append(content, DATE, "My Plan", "done")
    assert line is not None
    assert new_content.split("\n")[line - 1] == _entry_line(new_content)
    assert "## Completed Work (2026-07-31)" in new_content


def test_existing_section_for_date_appends_into_it() -> None:
    content = f"# Active Context\n\n## Completed Work ({DATE})\n\n- old\n"
    new_content, line = create_section_and_append(content, DATE, "My Plan", "done")
    assert line is not None
    assert new_content.count(f"## Completed Work ({DATE})") == 1
    assert new_content.split("\n")[line - 1] == _entry_line(new_content)


def test_missing_heading_appends_section_at_end() -> None:
    """No Completed Work heading at all: create one rather than failing."""
    content = "# Active Context\n\n## Current Focus\n\nstuff\n"
    new_content, line = create_section_and_append(content, DATE, "My Plan", "done")
    assert line is not None
    assert f"## Completed Work ({DATE})" in new_content
    assert new_content.split("\n")[line - 1] == _entry_line(new_content)
