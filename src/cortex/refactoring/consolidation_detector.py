"""
Consolidation Detector for MCP Memory Bank

This module detects opportunities to consolidate duplicate or similar content
across multiple files using transclusion and shared sections.
"""

import hashlib
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.constants import CONSOLIDATION_MIN_SIMILARITY
from cortex.refactoring.consolidation_detector_models import ConsolidationOpportunity
from cortex.refactoring.consolidation_detector_opportunities import (
    build_duplicate_opportunity,
    build_shared_pattern_opportunity,
    build_similar_section_opportunity,
    impact_benefits_risks,
)
from cortex.refactoring.consolidation_detector_similarity import (
    calculate_similarity as _calculate_similarity,
)
from cortex.refactoring.consolidation_detector_similarity import (
    compute_content_hash as _compute_content_hash_raw,
)
from cortex.refactoring.consolidation_detector_similarity import (
    extract_common_content as _extract_common_content,
)
from cortex.refactoring.consolidation_detector_similarity import (
    extract_common_content_multi as _extract_common_content_multi,
)
from cortex.refactoring.consolidation_detector_similarity import (
    find_common_prefix as _find_common_prefix,
)
from cortex.refactoring.consolidation_detector_similarity import (
    get_differences as _get_differences,
)
from cortex.refactoring.consolidation_detector_similarity import (
    slugify as _slugify,
)
from cortex.refactoring.models import ConsolidationImpactModel, RiskLevel

__all__ = ["ConsolidationDetector", "ConsolidationOpportunity"]


class ConsolidationDetector:
    """
    Detects consolidation opportunities in Memory Bank files.

    Identifies:
    - Exact duplicate sections across files
    - Similar content that could be consolidated
    - Common patterns that could use transclusion
    - Shared sections that should be extracted
    """

    def __init__(
        self,
        memory_bank_path: Path,
        min_similarity: float = CONSOLIDATION_MIN_SIMILARITY,
        min_section_length: int = 100,
        target_reduction: float = 0.30,
    ):
        """
        Initialize the consolidation detector.

        Args:
            memory_bank_path: Path to Memory Bank directory
            min_similarity: Minimum similarity score for consolidation (0-1)
            min_section_length: Minimum section length to consider (chars)
            target_reduction: Target token reduction (0-1)
        """
        self.memory_bank_path: Path = Path(memory_bank_path)
        self.min_similarity: float = min_similarity
        self.min_section_length: int = min_section_length
        self.target_reduction: float = target_reduction

        self.opportunity_counter: int = 0
        self._content_hash_cache: dict[str, str] = {}
        self._similarity_cache: dict[tuple[str, str], float] = {}

    def _compute_content_hash(self, content: str) -> str:
        """Compute fast hash of content with caching."""
        if content in self._content_hash_cache:
            return self._content_hash_cache[content]
        content_hash = _compute_content_hash_raw(content)
        self._content_hash_cache[content] = content_hash
        return content_hash

    def generate_opportunity_id(self) -> str:
        """Generate unique opportunity ID"""
        self.opportunity_counter += 1
        return f"CONS-{self.opportunity_counter:04d}"

    def generate_extraction_target(
        self, heading: str, affected_files: list[str]
    ) -> str:
        """Generate a path for extracted content"""
        slug = self.slugify(heading)
        file_names = [Path(f).stem for f in affected_files]
        if len(file_names) > 1:
            common_prefix = self.find_common_prefix(file_names)
            if common_prefix and len(common_prefix) > 3:
                return f"memory-bank/shared-{common_prefix}-{slug}.md"
        return f"memory-bank/shared-{slug}.md"

    async def detect_opportunities(
        self,
        files: list[str] | None = None,
        suggest_transclusion: bool = True,  # noqa: ARG002
    ) -> list[ConsolidationOpportunity]:
        """Detect consolidation opportunities across files."""
        if files is None:
            files = await self.get_all_markdown_files()

        file_contents = await self._read_files_for_detection(files)
        opportunities = await self._detect_all_opportunity_types(file_contents)
        opportunities.sort(key=lambda o: o.token_savings, reverse=True)
        return opportunities

    async def _read_files_for_detection(self, files: list[str]) -> dict[str, str]:
        """Read all files for detection."""
        file_contents: dict[str, str] = {}
        for file_path in files:
            try:
                content = await self.read_file(file_path)
                file_contents[file_path] = content
            except Exception as e:
                from cortex.core.logging_config import logger

                logger.warning(
                    f"Failed to read file {file_path} for consolidation detection: {e}"
                )
        return file_contents

    async def _detect_all_opportunity_types(
        self, file_contents: dict[str, str]
    ) -> list[ConsolidationOpportunity]:
        """Detect all types of consolidation opportunities."""
        opportunities: list[ConsolidationOpportunity] = []
        opportunities.extend(await self.detect_exact_duplicates(file_contents))
        opportunities.extend(await self.detect_similar_sections(file_contents))
        opportunities.extend(await self.detect_shared_patterns(file_contents))
        return opportunities

    async def get_all_markdown_files(self) -> list[str]:
        """Get all markdown files in Memory Bank"""
        files: list[str] = []
        if self.memory_bank_path.exists():
            for file_path in self.memory_bank_path.rglob("*.md"):
                if file_path.is_file():
                    files.append(str(file_path))
        return files

    async def read_file(self, file_path: str) -> str:
        """Read file contents"""
        try:
            full_path = (
                Path(file_path)
                if Path(file_path).is_absolute()
                else self.memory_bank_path / file_path
            )
            async with open_async_text_file(full_path, "r", "utf-8") as f:
                return await f.read()
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to read file {file_path}: {e}")
            return ""

    async def detect_exact_duplicates(
        self, file_contents: dict[str, str]
    ) -> list[ConsolidationOpportunity]:
        file_sections = self._parse_all_files_into_sections(file_contents)
        section_hashes = self._build_section_hashes(file_sections)
        return self._create_opportunities_from_hashes(section_hashes)

    def _parse_files_into_sections(
        self, file_contents: dict[str, str]
    ) -> dict[str, list[tuple[str, str]]]:
        """Parse all files into sections."""
        file_sections: dict[str, list[tuple[str, str]]] = {}
        for file_path, content in file_contents.items():
            file_sections[file_path] = self.parse_sections(content)
        return file_sections

    def _calculate_similarity_with_cache(
        self, content1: str, content2: str, hash1: str, hash2: str
    ) -> float:
        if hash1 == hash2:
            return 1.0
        cache_key = (hash1, hash2)
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]
        similarity = self.calculate_similarity(content1, content2)
        self._similarity_cache[cache_key] = similarity
        return similarity

    def _compare_sections_for_similarity(
        self,
        file1: str,
        file2: str,
        sections1: list[tuple[str, str]],
        sections2: list[tuple[str, str]],
    ) -> list[ConsolidationOpportunity]:
        """Compare sections between two files for similarity."""
        opportunities: list[ConsolidationOpportunity] = []
        sections2_with_hashes = self._precompute_section_hashes(sections2)

        for heading1, content1 in sections1:
            if len(content1) < self.min_section_length:
                continue
            hash1 = self._compute_content_hash(content1)

            for heading2, content2, hash2 in sections2_with_hashes:
                similarity = self._calculate_similarity_with_cache(
                    content1, content2, hash1, hash2
                )
                if similarity >= self.min_similarity:
                    opportunity = build_similar_section_opportunity(
                        self,
                        file1,
                        file2,
                        heading1,
                        heading2,
                        content1,
                        content2,
                        similarity,
                    )
                    opportunities.append(opportunity)

        return opportunities

    def _precompute_section_hashes(
        self, sections: list[tuple[str, str]]
    ) -> list[tuple[str, str, str]]:
        sections_with_hashes: list[tuple[str, str, str]] = []
        for heading, content in sections:
            if len(content) < self.min_section_length:
                continue
            content_hash = self._compute_content_hash(content)
            sections_with_hashes.append((heading, content, content_hash))
        return sections_with_hashes

    async def detect_similar_sections(
        self, file_contents: dict[str, str]
    ) -> list[ConsolidationOpportunity]:
        """Detect similar (not exact) sections across files"""
        opportunities: list[ConsolidationOpportunity] = []
        file_sections = self._parse_files_into_sections(file_contents)
        compared_pairs: set[tuple[str, str]] = set()

        for file1, sections1 in file_sections.items():
            for file2, sections2 in file_sections.items():
                if file1 >= file2:
                    continue
                pair_key: tuple[str, str] = (file1, file2)
                if pair_key in compared_pairs:
                    continue
                compared_pairs.add(pair_key)
                section_opportunities = self._compare_sections_for_similarity(
                    file1, file2, sections1, sections2
                )
                opportunities.extend(section_opportunities)

        return opportunities

    def _collect_heading_occurrences(
        self, file_contents: dict[str, str]
    ) -> dict[str, list[tuple[str, str]]]:
        heading_occurrences: dict[str, list[tuple[str, str]]] = {}
        for file_path, content in file_contents.items():
            sections = self.parse_sections(content)
            for heading, section_content in sections:
                normalized_heading = heading.lower().strip()
                if normalized_heading not in heading_occurrences:
                    heading_occurrences[normalized_heading] = []
                heading_occurrences[normalized_heading].append(
                    (file_path, section_content)
                )
        return heading_occurrences

    def _calculate_average_similarity(self, contents: list[str]) -> float | None:
        if not contents:
            return None
        content_hashes = [self._compute_content_hash(c) for c in contents]
        similarities: list[float] = []
        for i, (content1, hash1) in enumerate(
            zip(contents, content_hashes, strict=True)
        ):
            for j in range(i + 1, len(contents)):
                similarity = self._calculate_similarity_with_cache(
                    content1, contents[j], hash1, content_hashes[j]
                )
                similarities.append(similarity)
        if not similarities:
            return None
        return sum(similarities) / len(similarities)

    async def detect_shared_patterns(
        self, file_contents: dict[str, str]
    ) -> list[ConsolidationOpportunity]:
        """Detect shared patterns or repeated content structures"""
        opportunities: list[ConsolidationOpportunity] = []
        heading_occurrences = self._collect_heading_occurrences(file_contents)

        for heading, occurrences in heading_occurrences.items():
            if len(occurrences) < 2:
                continue
            contents = [occ[1] for occ in occurrences]
            if not contents or any(len(c) < self.min_section_length for c in contents):
                continue
            avg_similarity = self._calculate_average_similarity(contents)
            if avg_similarity is None:
                continue
            if avg_similarity >= self.min_similarity * 0.8:
                opportunity = build_shared_pattern_opportunity(
                    self, heading, occurrences, avg_similarity
                )
                opportunities.append(opportunity)

        return opportunities

    def parse_sections(self, content: str) -> list[tuple[str, str]]:
        """Parse markdown content into sections"""
        sections: list[tuple[str, str]] = []
        lines = content.split("\n")
        current_heading = "Introduction"
        current_content: list[str] = []

        for line in lines:
            if line.startswith("#"):
                if current_content:
                    sections.append((current_heading, "\n".join(current_content)))
                current_heading = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append((current_heading, "\n".join(current_content)))
        return sections

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        return _calculate_similarity(text1, text2)

    def extract_common_content(self, text1: str, text2: str) -> str:
        """Extract common content from two texts"""
        return _extract_common_content(text1, text2)

    def extract_common_content_multi(self, texts: list[str]) -> str:
        """Extract common content from multiple texts"""
        return _extract_common_content_multi(texts)

    def get_differences(self, text1: str, text2: str) -> list[str]:
        """Get list of differences between two texts"""
        return _get_differences(text1, text2)

    def find_common_prefix(self, strings: list[str]) -> str:
        """Find common prefix in list of strings"""
        return _find_common_prefix(strings)

    def slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug"""
        return _slugify(text)

    async def analyze_consolidation_impact(
        self, opportunity: ConsolidationOpportunity
    ) -> ConsolidationImpactModel:
        """Analyze the impact of applying a consolidation."""
        risk_level = (
            RiskLevel.LOW if opportunity.similarity_score > 0.95 else RiskLevel.MEDIUM
        )
        benefits, risks = impact_benefits_risks(opportunity)
        return ConsolidationImpactModel(
            opportunity_id=opportunity.opportunity_id,
            token_savings=opportunity.token_savings,
            files_affected=len(opportunity.affected_files),
            extraction_required=True,
            transclusion_count=len(opportunity.transclusion_syntax),
            similarity_score=opportunity.similarity_score,
            risk_level=risk_level,
            benefits=benefits,
            risks=risks,
        )

    def _parse_all_files_into_sections(
        self, file_contents: dict[str, str]
    ) -> dict[str, list[tuple[str, str]]]:
        return self._parse_files_into_sections(file_contents)

    def _build_section_hashes(
        self, file_sections: dict[str, list[tuple[str, str]]]
    ) -> dict[str, list[tuple[str, str, str]]]:
        section_hashes: dict[str, list[tuple[str, str, str]]] = {}
        for file_path, sections in file_sections.items():
            for heading, content in sections:
                if len(content) < self.min_section_length:
                    continue
                content_hash = hashlib.md5(content.encode()).hexdigest()
                if content_hash not in section_hashes:
                    section_hashes[content_hash] = []
                section_hashes[content_hash].append((file_path, heading, content))
        return section_hashes

    def _create_opportunities_from_hashes(
        self, section_hashes: dict[str, list[tuple[str, str, str]]]
    ) -> list[ConsolidationOpportunity]:
        opportunities: list[ConsolidationOpportunity] = []
        for content_hash, occurrences in section_hashes.items():
            if len(occurrences) < 2:
                continue
            opportunity = build_duplicate_opportunity(self, content_hash, occurrences)
            opportunities.append(opportunity)
        return opportunities
