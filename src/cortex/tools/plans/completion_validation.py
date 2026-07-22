"""Validation helpers for plan completion.

Handles date format and progress entry format validation.
"""

from datetime import datetime


def validate_date_str(date_str: str) -> str | None:
    """Validate date_str is YYYY-MM-DD. Returns error message if invalid, None if valid."""
    if not date_str or not date_str.strip():
        return "Date is required (YYYY-MM-DD)."
    s = date_str.strip()
    if len(s) != 10 or s[4] != "-" or s[7] != "-":
        return "Date must be YYYY-MM-DD (e.g. 2026-02-20)."
    try:
        _ = datetime.strptime(s, "%Y-%m-%d")
        return None
    except ValueError:
        return "Date must be a valid calendar date (YYYY-MM-DD)."


def validate_progress_entry_text(entry_text: str) -> str | None:
    """Reject progress entry text that matches common corruption patterns.

    Ensures COMPLETE is preceded by the proper delimiter (e.g. " - COMPLETE"
    or ")** - COMPLETE") to avoid malformed bullets like "20260209COMPLETE".
    The title segment (everything before " - COMPLETE") is rejected only when
    it contains an unclosed '(' (more '(' than ')'), which catches a
    truncated "(date" suffix. A balanced, fully-closed parenthesis anywhere
    in the title — e.g. "plan(graph)" used as ordinary title text, or a
    proper "(date)** - COMPLETE" suffix — is valid and is not rejected.
    Returns an error message if invalid, None if valid.
    """
    t = (entry_text or "").strip()
    if "COMPLETE" in t and " - COMPLETE" not in t:
        return (
            "Progress entry contains 'COMPLETE' but is missing ' - COMPLETE' "
            "(e.g. use '**Title** - COMPLETE. Summary...', not '...COMPLETE' alone)"
        )
    if " - COMPLETE" in t:
        title_part = t.split(" - COMPLETE", 1)[0]
        if title_part.count("(") > title_part.count(")"):
            return (
                "Progress entry has an unclosed '(' before ' - COMPLETE'. "
                "Use '**Title (date)** - COMPLETE. Summary...' so the title segment is closed."
            )
    return None
