"""Validate complete ISO date tokens without discarding provenance precision."""

import re
from collections.abc import Callable
from datetime import datetime

from cortex.validation.timestamp_models import TimestampViolationModel

# AI: Consume malformed suffixes too, so a valid prefix cannot hide a bad time.
ISO_TOKEN = re.compile(
    r"(?<![\w/-])\d{4}-\d{2}-\d{2}"
    + r"(?:(?:T[^\s,;()\[\]{}<>\"'`*|]*"
    + r"|[ \t]+(?=\d+:)[^\s,;()\[\]{}<>\"'`*|]*)(?:[ \t]+UTC\b)?)?"
    + r"(?![\w/-])"
)
CANONICAL = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?")
PROVENANCE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}"
    + r"(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2}| UTC)?)?"
)


def _valid_time_range(token: str) -> bool | None:
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})Z?[-/](\d{2}:\d{2})(?:Z| UTC)", token
    )
    if match is None:
        return None
    try:
        _ = datetime.fromisoformat(f"{match[1]}T{match[2]}Z")
        _ = datetime.fromisoformat(f"{match[1]}T{match[3]}Z")
        # AI: A smaller ending clock denotes the following UTC day.
        return True
    except ValueError:
        return False


def _valid_calendar(token: str) -> bool:
    time_range = _valid_time_range(token)
    if time_range is not None:
        return time_range
    if PROVENANCE.fullmatch(token) is None:
        return False
    offset = re.search(r"[+-](\d{2}):(\d{2})$", token)
    if offset and (int(offset[1]) > 23 or int(offset[2]) > 59):
        return False
    try:
        _ = datetime.fromisoformat(token.replace(" UTC", "+00:00"))
        return True
    except ValueError:
        return False


def _is_run_identifier(token: str, prefix: str) -> bool:
    if (
        re.search(r"\b(?:analysis|pipeline|run|session|artifact)\b", prefix, re.I)
        is None
    ):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}", token) is None:
        return False
    try:
        _ = datetime.strptime(token, "%Y-%m-%dT%H-%M")
        return True
    except ValueError:
        return False


def check_iso_timestamps(
    line: str,
    line_num: int,
    is_work: Callable[[str, int, int], bool],
) -> tuple[int, list[TimestampViolationModel]]:
    """Keep entry metadata canonical; preserve validated prose citations intact."""
    valid = 0
    violations: list[TimestampViolationModel] = []
    for match in ISO_TOKEN.finditer(line):
        token = match.group()
        # AI: Trim prose punctuation only after proving the complete base valid.
        if token.endswith((".", ":")) and _valid_calendar(token[:-1]):
            token = token[:-1]
        strict = is_work(line, match.start(), match.end())
        if not strict and _is_run_identifier(token, line[: match.start()]):
            continue
        calendar_valid = _valid_calendar(token)
        if calendar_valid and (not strict or CANONICAL.fullmatch(token)):
            valid += 1
            continue
        issue = (
            "Invalid calendar date/time"
            if not calendar_valid
            else ("Work timestamp must use YYYY-MM-DD or YYYY-MM-DDTHH:MM")
        )
        violations.append(
            TimestampViolationModel(
                line=line_num, content=line.strip()[:80], timestamp=token, issue=issue
            )
        )
    return valid, violations
