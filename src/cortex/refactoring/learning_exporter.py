#!/usr/bin/env python3
"""Learning data exporter for learned patterns.

This module handles exporting learned patterns in various formats.
"""

from datetime import datetime

from cortex.core.models import ModelDict

from .learning_data_manager import LearnedPattern


def export_learned_patterns(
    patterns: dict[str, LearnedPattern], format: str = "json"
) -> ModelDict:
    """
    Export learned patterns.

    Args:
        patterns: Dictionary of learned patterns
        format: Export format ("json", "text")

    Returns:
        Exported patterns dictionary
    """
    if format == "json":
        return _export_patterns_json(patterns)
    elif format == "text":
        return _export_patterns_text(patterns)
    else:
        return {
            "error": f"Unsupported format: {format}",
            "supported_formats": ["json", "text"],
        }


def _export_patterns_json(patterns: dict[str, LearnedPattern]) -> ModelDict:
    """Export patterns in JSON format."""
    return {
        "patterns": {
            pattern_id: pattern.to_dict() for pattern_id, pattern in patterns.items()
        },
        "export_date": datetime.now().isoformat(),
    }


def _export_patterns_text(patterns: dict[str, LearnedPattern]) -> ModelDict:
    """Export patterns in text format."""
    lines: list[str] = ["# Learned Patterns\n"]
    lines.append(f"Export Date: {datetime.now().isoformat()}\n\n")

    for pattern in patterns.values():
        _append_pattern_text(lines, pattern)

    return {
        "content": "".join(lines),
        "export_date": datetime.now().isoformat(),
    }


def _append_pattern_text(lines: list[str], pattern: LearnedPattern) -> None:
    """Append pattern information to text lines."""
    lines.append(f"## {pattern.pattern_id}\n")
    lines.append(f"- Type: {pattern.pattern_type}\n")
    lines.append(f"- Success Rate: {pattern.success_rate:.1%}\n")
    lines.append(f"- Occurrences: {pattern.total_occurrences}\n")
    lines.append(f"- Approved: {pattern.approved_count}\n")
    lines.append(f"- Rejected: {pattern.rejected_count}\n")
    lines.append(f"- Confidence Adjustment: {pattern.confidence_adjustment:+.2f}\n")
    lines.append("\n")
