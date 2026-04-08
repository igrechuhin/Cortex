"""Word-count harness for sample pipeline_handoff-style JSON payloads (manual baseline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures" / "brevity_pipeline_samples"
)


def _payload_word_count(obj: object) -> int:
    """Approximate token proxy: split on whitespace in all string values."""
    if isinstance(obj, str):
        return len(obj.split())
    if isinstance(obj, dict):
        mapping = cast(dict[str, object], obj)
        return sum(_payload_word_count(v) for v in mapping.values())
    if isinstance(obj, list):
        seq = cast(list[object], obj)
        return sum(_payload_word_count(v) for v in seq)
    return 0


def test_brevity_samples_word_counts() -> None:
    """Five fixtures exist; per-payload and average word counts are computable."""
    paths = sorted(_FIXTURE_DIR.glob("sample_*.json"))
    assert len(paths) == 5
    counts: list[int] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        counts.append(_payload_word_count(data))
    assert all(c > 0 for c in counts)
    average = sum(counts) / len(counts)
    assert average > 0
