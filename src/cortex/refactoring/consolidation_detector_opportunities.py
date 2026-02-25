"""
Opportunity-building helpers for consolidation detection.

Extracted from consolidation_detector.py for file size compliance.
"""

from pathlib import Path
from typing import Protocol, cast

from cortex.core.models import JsonValue, ModelDict
from cortex.refactoring.consolidation_detector_models import ConsolidationOpportunity
from cortex.refactoring.consolidation_detector_similarity import (
    extract_common_content,
    extract_common_content_multi,
    get_differences,
    slugify,
)


class _DetectorProtocol(Protocol):
    """Minimal detector interface to avoid circular import."""

    def generate_opportunity_id(self) -> str: ...
    def generate_extraction_target(
        self, heading: str, affected_files: list[str]
    ) -> str: ...


def _build_transclusion_syntax(extraction_target: str, heading: str) -> list[str]:
    """Build transclusion syntax for opportunity."""
    return [
        f"{{{{include: {Path(extraction_target).name}#{slugify(heading)}}}}}"
        for _ in range(2)
    ]


def _build_transclusion_syntax_multi(
    extraction_target: str, heading: str, files: list[str]
) -> list[str]:
    """Build transclusion syntax list for multiple files."""
    return [
        f"{{{{include: {Path(extraction_target).name}#{slugify(heading)}}}}}"
        for _ in files
    ]


def _prepare_consolidation_data(
    occurrences: list[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """Prepare files and contents lists from occurrences."""
    files = [occ[0] for occ in occurrences]
    contents = [occ[1] for occ in occurrences]
    return files, contents


def build_similar_section_opportunity(
    detector: _DetectorProtocol,
    file1: str,
    file2: str,
    heading1: str,
    heading2: str,
    content1: str,
    content2: str,
    similarity: float,
) -> ConsolidationOpportunity:
    """Build a consolidation opportunity for similar sections."""
    common_content = extract_common_content(content1, content2)
    token_savings = int(len(common_content) / 4)
    extraction_target = detector.generate_extraction_target(heading1, [file1, file2])
    transclusion_syntax = _build_transclusion_syntax(extraction_target, heading1)

    return _create_consolidation_opportunity(
        detector,
        file1,
        file2,
        heading1,
        heading2,
        content1,
        content2,
        similarity,
        common_content,
        token_savings,
        extraction_target,
        transclusion_syntax,
    )


def _build_consolidation_details(
    heading1: str, heading2: str, content1: str, content2: str
) -> ModelDict:
    """Build consolidation opportunity details."""
    differences_json = cast(list[JsonValue], get_differences(content1, content2))
    return {
        "heading1": heading1,
        "heading2": heading2,
        "differences": differences_json,
    }


def _create_consolidation_opportunity(
    detector: _DetectorProtocol,
    file1: str,
    file2: str,
    heading1: str,
    heading2: str,
    content1: str,
    content2: str,
    similarity: float,
    common_content: str,
    token_savings: int,
    extraction_target: str,
    transclusion_syntax: list[str],
) -> ConsolidationOpportunity:
    """Create consolidation opportunity object."""
    return ConsolidationOpportunity(
        opportunity_id=detector.generate_opportunity_id(),
        opportunity_type="similar_content",
        affected_files=[file1, file2],
        common_content=common_content,
        similarity_score=similarity,
        token_savings=token_savings,
        suggested_action="Consolidate similar sections and use transclusion",
        extraction_target=extraction_target,
        transclusion_syntax=transclusion_syntax,
        details=_build_consolidation_details(heading1, heading2, content1, content2),
    )


def build_shared_pattern_opportunity(
    detector: _DetectorProtocol,
    heading: str,
    occurrences: list[tuple[str, str]],
    avg_similarity: float,
) -> ConsolidationOpportunity:
    """Build a consolidation opportunity for shared patterns."""
    files, contents = _prepare_consolidation_data(occurrences)
    common_content = extract_common_content_multi(contents)
    token_savings = int(len(common_content) / 4) * (len(occurrences) - 1)
    extraction_target = detector.generate_extraction_target(heading, files)
    transclusion_syntax = _build_transclusion_syntax_multi(
        extraction_target, heading, files
    )

    return ConsolidationOpportunity(
        opportunity_id=detector.generate_opportunity_id(),
        opportunity_type="shared_section",
        affected_files=files,
        common_content=common_content,
        similarity_score=avg_similarity,
        token_savings=token_savings,
        suggested_action=(
            f"Create shared section for '{heading}' and use transclusion"
        ),
        extraction_target=extraction_target,
        transclusion_syntax=transclusion_syntax,
        details={
            "heading": heading,
            "occurrences": len(occurrences),
            "average_similarity": avg_similarity,
        },
    )


def _build_duplicate_opportunity_details(
    heading: str, occurrences: list[tuple[str, str, str]], content_hash: str
) -> ModelDict:
    """Build details dict for duplicate opportunity."""
    return {
        "heading": heading,
        "occurrences": len(occurrences),
        "content_hash": content_hash,
    }


def build_duplicate_opportunity(
    detector: _DetectorProtocol,
    content_hash: str,
    occurrences: list[tuple[str, str, str]],
) -> ConsolidationOpportunity:
    """Build consolidation opportunity from duplicate occurrences."""
    files = list(dict.fromkeys([occ[0] for occ in occurrences]))
    heading = occurrences[0][1]
    content = occurrences[0][2]
    token_savings = int(len(content) / 4) * (len(occurrences) - 1)
    extraction_target = detector.generate_extraction_target(heading, files)
    transclusion_syntax = _build_transclusion_syntax_multi(
        extraction_target, heading, files
    )
    return ConsolidationOpportunity(
        opportunity_id=detector.generate_opportunity_id(),
        opportunity_type="exact_duplicate",
        affected_files=files,
        common_content=content,
        similarity_score=1.0,
        token_savings=token_savings,
        suggested_action=(
            f"Extract section '{heading}' to shared file and use transclusion"
        ),
        extraction_target=extraction_target,
        transclusion_syntax=transclusion_syntax,
        details=_build_duplicate_opportunity_details(
            heading, occurrences, content_hash
        ),
    )


def impact_benefits_risks(
    opportunity: ConsolidationOpportunity,
) -> tuple[list[str], list[str]]:
    """Return (benefits, risks) lists for consolidation impact."""
    benefits = [
        f"Save ~{opportunity.token_savings} tokens",
        f"Reduce duplication across {len(opportunity.affected_files)} files",
        "Single source of truth for shared content",
        "Easier maintenance and updates",
    ]
    risks = (
        [
            "Requires understanding of transclusion syntax",
            "May break if shared file is deleted",
            "Circular dependencies if not careful",
        ]
        if opportunity.similarity_score < 0.95
        else ["Low risk - exact duplicates found"]
    )
    return benefits, risks
