"""
Consolidation Detector for MCP Memory Bank

This module detects opportunities to consolidate duplicate or similar content
across multiple files using transclusion and shared sections.
"""

import hashlib
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from cortex.core.async_file_utils import open_async_text_file


@dataclass
class ConsolidationOpportunity:
    """Represents an opportunity to consolidate content"""

    opportunity_id: str
    opportunity_type: str  # "exact_duplicate", "similar_content", "shared_section"
    affected_files: list[str]
    common_content: str
    similarity_score: float  # 0-1
    token_savings: int
    suggested_action: str
    extraction_target: str  # Where to extract the common content
    transclusion_syntax: list[str]  # Transclusion syntax for each file
    details: dict[str, object] = field(default_factory=lambda: {})

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary"""
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "affected_files": self.affected_files,
            "common_content_preview": (
                self.common_content[:200] + "..."
                if len(self.common_content) > 200
                else self.common_content
            ),
            "similarity_score": self.similarity_score,
            "token_savings": self.token_savings,
            "suggested_action": self.suggested_action,
            "extraction_target": self.extraction_target,
            "transclusion_syntax": self.transclusion_syntax,
            "details": self.details,
        }


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
        min_similarity: float = 0.80,
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
        # Performance optimization: Cache for content hashes
        self._content_hash_cache: dict[str, str] = {}
        # Performance optimization: Cache for similarity calculations
        self._similarity_cache: dict[tuple[str, str], float] = {}

    def _compute_content_hash(self, content: str) -> str:
        """
        Compute fast hash of content for quick equality checks.

        Performance: O(n) where n is content length.
        Uses SHA-256 for collision resistance.

        Args:
            content: Text content to hash

        Returns:
            Hex digest of content hash
        """
        # Check cache first
        if content in self._content_hash_cache:
            return self._content_hash_cache[content]

        # Compute and cache
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        self._content_hash_cache[content] = content_hash
        return content_hash

    def generate_opportunity_id(self) -> str:
        """Generate unique opportunity ID"""
        self.opportunity_counter += 1
        return f"CONS-{self.opportunity_counter:04d}"

    async def detect_opportunities(
        self,
        files: list[str] | None = None,
        suggest_transclusion: bool = True,  # noqa: ARG002
    ) -> list[ConsolidationOpportunity]:
        """
        Detect consolidation opportunities across files.

        Args:
            files: List of file paths to analyze (all if None)
            suggest_transclusion: Whether to suggest transclusion syntax

        Returns:
            List of consolidation opportunities
        """
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

        exact_dupes = await self.detect_exact_duplicates(file_contents)
        opportunities.extend(exact_dupes)

        similar_sections = await self.detect_similar_sections(file_contents)
        opportunities.extend(similar_sections)

        shared_patterns = await self.detect_shared_patterns(file_contents)
        opportunities.extend(shared_patterns)

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
            # Handle both absolute and relative paths
            if Path(file_path).is_absolute():
                full_path = Path(file_path)
            else:
                full_path = self.memory_bank_path / file_path
            async with open_async_text_file(full_path, "r", "utf-8") as f:
                return await f.read()
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to read file {file_path}: {e}")
            return ""

    async def detect_exact_duplicates(
        self, file_contents: dict[str, str]
    ) -> list[ConsolidationOpportunity]:
        """Detect exact duplicate sections across files"""
        file_sections = self._parse_all_files_into_sections(file_contents)
        section_hashes = self._build_section_hashes(file_sections)
        return self._create_opportunities_from_hashes(section_hashes)

    def _parse_files_into_sections(
        self, file_contents: dict[str, str]
    ) -> dict[str, list[tuple[str, str]]]:
        """Parse all files into sections.

        Args:
            file_contents: Dictionary of file paths to content

        Returns:
            Dictionary of file paths to section lists
        """
        file_sections: dict[str, list[tuple[str, str]]] = {}
        for file_path, content in file_contents.items():
            sections = self.parse_sections(content)
            file_sections[file_path] = sections
        return file_sections

    def _build_similar_section_opportunity(
        self,
        file1: str,
        file2: str,
        heading1: str,
        heading2: str,
        content1: str,
        content2: str,
        similarity: float,
    ) -> ConsolidationOpportunity:
        """Build a consolidation opportunity for similar sections.

        Args:
            file1: First file path
            file2: Second file path
            heading1: First section heading
            heading2: Second section heading
            content1: First section content
            content2: Second section content
            similarity: Similarity score

        Returns:
            ConsolidationOpportunity instance
        """
        common_content = self.extract_common_content(content1, content2)
        token_savings = int(len(common_content) / 4)
        extraction_target = self.generate_extraction_target(heading1, [file1, file2])
        transclusion_syntax = self._build_transclusion_syntax(
            extraction_target, heading1
        )

        return self._create_consolidation_opportunity(
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

    def _create_consolidation_opportunity(
        self,
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
            opportunity_id=self.generate_opportunity_id(),
            opportunity_type="similar_content",
            affected_files=[file1, file2],
            common_content=common_content,
            similarity_score=similarity,
            token_savings=token_savings,
            suggested_action="Consolidate similar sections and use transclusion",
            extraction_target=extraction_target,
            transclusion_syntax=transclusion_syntax,
            details={
                "heading1": heading1,
                "heading2": heading2,
                "differences": self.get_differences(content1, content2),
            },
        )

    def _build_transclusion_syntax(
        self, extraction_target: str, heading1: str
    ) -> list[str]:
        """Build transclusion syntax for opportunity."""
        return [
            f"{{{{include: {Path(extraction_target).name}#{self.slugify(heading1)}}}}}"
            for _ in range(2)
        ]

    def _compare_sections_for_similarity(
        self,
        file1: str,
        file2: str,
        sections1: list[tuple[str, str]],
        sections2: list[tuple[str, str]],
    ) -> list[ConsolidationOpportunity]:
        """Compare sections between two files for similarity.

        Performance optimization: Uses content hashing for fast exact-match detection
        and early exit. Reduces O(sections1 × sections2 × content_length) to
        O(sections1 + sections2) for exact matches, O(sections1 × sections2) for similar.

        Args:
            file1: First file path
            file2: Second file path
            sections1: Sections from first file
            sections2: Sections from second file

        Returns:
            List of consolidation opportunities found
        """
        opportunities: list[ConsolidationOpportunity] = []
        sections2_with_hashes = self._precompute_section_hashes(sections2)

        for heading1, content1 in sections1:
            if len(content1) < self.min_section_length:
                continue

            # Compute hash once for content1
            hash1 = self._compute_content_hash(content1)

            for heading2, content2, hash2 in sections2_with_hashes:
                # Performance optimization: Fast exact-match check using hashes
                # Avoids expensive SequenceMatcher for identical content
                if hash1 == hash2:
                    # Exact match - similarity is 1.0
                    similarity = 1.0
                else:
                    # Different content - check cache first, then compute
                    cache_key = (hash1, hash2)
                    if cache_key in self._similarity_cache:
                        similarity = self._similarity_cache[cache_key]
                    else:
                        similarity = self.calculate_similarity(content1, content2)
                        # Cache the result for future comparisons
                        self._similarity_cache[cache_key] = similarity

                # Early termination: Only create opportunities if similarity meets threshold
                if similarity >= self.min_similarity:
                    opportunity = self._build_similar_section_opportunity(
                        file1, file2, heading1, heading2, content1, content2, similarity
                    )
                    opportunities.append(opportunity)

        return opportunities

    def _precompute_section_hashes(
        self, sections: list[tuple[str, str]]
    ) -> list[tuple[str, str, str]]:
        """Pre-compute hashes for sections to avoid repeated hashing."""
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
        """Collect all heading occurrences across files.

        Args:
            file_contents: Dictionary of file paths to content

        Returns:
            Dictionary mapping normalized headings to (file, content) tuples
        """
        heading_occurrences: dict[str, list[tuple[str, str]]] = {}

        for file_path, content in file_contents.items():
            sections: list[tuple[str, str]] = self.parse_sections(content)
            for heading, section_content in sections:
                normalized_heading = heading.lower().strip()
                if normalized_heading not in heading_occurrences:
                    heading_occurrences[normalized_heading] = []
                heading_occurrences[normalized_heading].append(
                    (file_path, section_content)
                )

        return heading_occurrences

    def _calculate_average_similarity(self, contents: list[str]) -> float | None:
        """Calculate average similarity between all pairs of contents.

        Performance optimization: Uses content hashing for fast exact-match detection
        and similarity caching. Reduces redundant SequenceMatcher calls.

        Args:
            contents: List of content strings to compare

        Returns:
            Average similarity score, or None if no valid comparisons
        """
        if not contents:
            return None

        # Performance optimization: Pre-compute hashes to group identical content
        # This reduces comparisons for duplicate content from O(n²) to O(n)
        content_hashes: list[str] = [self._compute_content_hash(c) for c in contents]

        similarities: list[float] = []
        for i, (content1, hash1) in enumerate(
            zip(contents, content_hashes, strict=True)
        ):
            for j in range(i + 1, len(contents)):
                content2 = contents[j]
                hash2 = content_hashes[j]

                # Fast exact-match check using hashes
                if hash1 == hash2:
                    similarity = 1.0
                else:
                    # Check cache first
                    cache_key = (hash1, hash2)
                    if cache_key in self._similarity_cache:
                        similarity = self._similarity_cache[cache_key]
                    else:
                        similarity = self.calculate_similarity(content1, content2)
                        self._similarity_cache[cache_key] = similarity

                similarities.append(similarity)

        if not similarities:
            return None

        return sum(similarities) / len(similarities)

    def _build_shared_pattern_opportunity(
        self,
        heading: str,
        occurrences: list[tuple[str, str]],
        avg_similarity: float,
    ) -> ConsolidationOpportunity:
        """Build a consolidation opportunity for shared patterns.

        Args:
            heading: Section heading
            occurrences: List of (file, content) tuples
            avg_similarity: Average similarity score

        Returns:
            ConsolidationOpportunity instance
        """
        files = [occ[0] for occ in occurrences]
        contents = [occ[1] for occ in occurrences]
        common_content = self.extract_common_content_multi(contents)
        token_savings = int(len(common_content) / 4) * (len(occurrences) - 1)
        extraction_target = self.generate_extraction_target(heading, files)

        transclusion_syntax = [
            f"{{{{include: {Path(extraction_target).name}#{self.slugify(heading)}}}}}"
            for _ in files
        ]

        return ConsolidationOpportunity(
            opportunity_id=self.generate_opportunity_id(),
            opportunity_type="shared_section",
            affected_files=files,
            common_content=common_content,
            similarity_score=avg_similarity,
            token_savings=token_savings,
            suggested_action=f"Create shared section for '{heading}' and use transclusion",
            extraction_target=extraction_target,
            transclusion_syntax=transclusion_syntax,
            details={
                "heading": heading,
                "occurrences": len(occurrences),
                "average_similarity": avg_similarity,
            },
        )

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
                opportunity = self._build_shared_pattern_opportunity(
                    heading, occurrences, avg_similarity
                )
                opportunities.append(opportunity)

        return opportunities

    def parse_sections(self, content: str) -> list[tuple[str, str]]:
        """Parse markdown content into sections"""
        sections: list[tuple[str, str]] = []
        lines: list[str] = content.split("\n")

        current_heading: str = "Introduction"
        current_content: list[str] = []

        for line in lines:
            # Check if line is a heading
            if line.startswith("#"):
                # Save previous section
                if current_content:
                    sections.append((current_heading, "\n".join(current_content)))

                # Start new section
                current_heading = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections.append((current_heading, "\n".join(current_content)))

        return sections

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        return SequenceMatcher(None, text1, text2).ratio()

    def extract_common_content(self, text1: str, text2: str) -> str:
        """Extract common content from two texts"""
        matcher = SequenceMatcher(None, text1, text2)
        common_parts: list[str] = []

        for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
            if tag == "equal":
                common_parts.append(text1[i1:i2])

        return "".join(common_parts)

    def extract_common_content_multi(self, texts: list[str]) -> str:
        """Extract common content from multiple texts"""
        if not texts:
            return ""

        # Start with first text, iteratively find common with others
        common = texts[0]
        for text in texts[1:]:
            common = self.extract_common_content(common, text)

        return common

    def get_differences(self, text1: str, text2: str) -> list[str]:
        """Get list of differences between two texts"""
        matcher = SequenceMatcher(None, text1, text2)
        differences: list[str] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                differences.append(f"{tag}: '{text1[i1:i2]}' vs '{text2[j1:j2]}'")

        return differences[:5]  # Limit to first 5 differences

    def generate_extraction_target(
        self, heading: str, affected_files: list[str]
    ) -> str:
        """Generate a path for extracted content"""
        # Use slugified heading as filename
        slug = self.slugify(heading)

        # Check if this is domain-specific
        file_names = [Path(f).stem for f in affected_files]

        # Try to find common prefix
        if len(file_names) > 1:
            common_prefix = self.find_common_prefix(file_names)
            if common_prefix and len(common_prefix) > 3:
                return f"memory-bank/shared-{common_prefix}-{slug}.md"

        return f"memory-bank/shared-{slug}.md"

    def find_common_prefix(self, strings: list[str]) -> str:
        """Find common prefix in list of strings"""
        if not strings:
            return ""

        prefix = strings[0]
        for s in strings[1:]:
            while not s.startswith(prefix) and prefix:
                prefix = prefix[:-1]

        return prefix

    def slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug"""
        # Convert to lowercase
        text = text.lower()
        # Replace spaces and special chars with hyphens
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        return text

    async def analyze_consolidation_impact(
        self, opportunity: ConsolidationOpportunity
    ) -> dict[str, object]:
        """
        Analyze the impact of applying a consolidation.

        Args:
            opportunity: The consolidation opportunity to analyze

        Returns:
            Impact analysis including token savings and risks
        """
        return {
            "opportunity_id": opportunity.opportunity_id,
            "token_savings": opportunity.token_savings,
            "files_affected": len(opportunity.affected_files),
            "extraction_required": True,
            "transclusion_count": len(opportunity.transclusion_syntax),
            "similarity_score": opportunity.similarity_score,
            "risk_level": "low" if opportunity.similarity_score > 0.95 else "medium",
            "benefits": [
                f"Save ~{opportunity.token_savings} tokens",
                f"Reduce duplication across {len(opportunity.affected_files)} files",
                "Single source of truth for shared content",
                "Easier maintenance and updates",
            ],
            "risks": (
                [
                    "Requires understanding of transclusion syntax",
                    "May break if shared file is deleted",
                    "Circular dependencies if not careful",
                ]
                if opportunity.similarity_score < 0.95
                else ["Low risk - exact duplicates found"]
            ),
        }

    def _parse_all_files_into_sections(
        self, file_contents: dict[str, str]
    ) -> dict[str, list[tuple[str, str]]]:
        """Parse all files into sections."""
        return self._parse_files_into_sections(file_contents)

    def _build_section_hashes(
        self, file_sections: dict[str, list[tuple[str, str]]]
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Build hash map of sections by content hash."""
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
        """Create consolidation opportunities from section hashes."""
        opportunities: list[ConsolidationOpportunity] = []
        for content_hash, occurrences in section_hashes.items():
            if len(occurrences) < 2:
                continue
            opportunity = self._build_duplicate_opportunity(content_hash, occurrences)
            opportunities.append(opportunity)
        return opportunities

    def _build_duplicate_opportunity(
        self, content_hash: str, occurrences: list[tuple[str, str, str]]
    ) -> ConsolidationOpportunity:
        """Build consolidation opportunity from duplicate occurrences."""
        files_raw = [occ[0] for occ in occurrences]
        files = list(dict.fromkeys(files_raw))
        heading = occurrences[0][1]
        content = occurrences[0][2]
        token_savings = int(len(content) / 4) * (len(occurrences) - 1)
        extraction_target = self.generate_extraction_target(heading, files)
        transclusion_syntax = [
            f"{{{{include: {Path(extraction_target).name}#{self.slugify(heading)}}}}}"
            for _ in files
        ]
        return ConsolidationOpportunity(
            opportunity_id=self.generate_opportunity_id(),
            opportunity_type="exact_duplicate",
            affected_files=files,
            common_content=content,
            similarity_score=1.0,
            token_savings=token_savings,
            suggested_action=f"Extract section '{heading}' to shared file and use transclusion",
            extraction_target=extraction_target,
            transclusion_syntax=transclusion_syntax,
            details={
                "heading": heading,
                "occurrences": len(occurrences),
                "content_hash": content_hash,
            },
        )
