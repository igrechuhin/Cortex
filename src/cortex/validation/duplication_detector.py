"""
Duplication detection for Memory Bank content.

This module detects duplicate or highly similar content across
Memory Bank files and suggests refactoring opportunities.
"""

import difflib
import hashlib
import re

from cortex.core.constants import (
    MIN_SECTION_LENGTH_CHARS,
    SIMILARITY_THRESHOLD_DUPLICATE,
)
from cortex.validation.models import (
    DuplicateEntry,
    DuplicationScanResult,
    HashMapEntry,
)


class DuplicationDetector:
    """Detect duplicate content across Memory Bank files."""

    def __init__(
        self,
        similarity_threshold: float = SIMILARITY_THRESHOLD_DUPLICATE,
        min_content_length: int = MIN_SECTION_LENGTH_CHARS,
    ):
        """
        Initialize duplication detector.

        Algorithm: Content similarity detection using hash-based grouping.
        Purpose: Efficiently find duplicate and similar sections across files.
        Complexity: O(n) for grouping + O(k²) for pairwise comparisons where k << n.
        Rationale: Hash-based grouping reduces comparisons from O(n²) to O(k²) per group.

        Args:
            similarity_threshold: Similarity score 0.0-1.0 to flag as duplicate
            min_content_length: Minimum chars to check for duplication
        """
        self.threshold: float = similarity_threshold
        self.min_length: int = min_content_length

    async def scan_all_files(
        self, files_content: dict[str, str]
    ) -> DuplicationScanResult:
        """
        Scan all files for duplications.

        Args:
            files_content: Dict mapping file names to their content

        Returns:
            DuplicationScanResult with duplicates found
        """
        # Extract sections from all files
        all_sections: dict[str, list[tuple[str, str]]] = {}
        for file_name, content in files_content.items():
            sections = self.extract_sections(content)
            all_sections[file_name] = sections

        # Find exact duplicates
        exact_duplicates = self.find_exact_duplicates(all_sections)

        # Find similar content
        similar_content = self.find_similar_content(all_sections)

        total_duplicates = len(exact_duplicates) + len(similar_content)

        return DuplicationScanResult(
            duplicates_found=total_duplicates,
            exact_duplicates=exact_duplicates,
            similar_content=similar_content,
        )

    def compare_sections(self, content1: str, content2: str) -> float:
        """
        Calculate similarity score between two content blocks.

        Args:
            content1: First content block
            content2: Second content block

        Returns:
            Similarity score 0.0-1.0
        """
        # Normalize content
        norm1 = self.normalize_content(content1)
        norm2 = self.normalize_content(content2)

        # Too short to compare
        if len(norm1) < self.min_length or len(norm2) < self.min_length:
            return 0.0

        return self.calculate_similarity(norm1, norm2)

    def extract_sections(self, content: str) -> list[tuple[str, str]]:
        """
        Extract sections from content.

        Args:
            content: File content

        Returns:
            List of (section_name, section_content) tuples
        """
        sections: list[tuple[str, str]] = []
        lines = content.split("\n")
        current_section = None
        current_content: list[str] = []

        for line in lines:
            # Check if it's a heading
            match = re.match(r"^(#{2,})\s+(.+)$", line)
            if match:
                # Save previous section if exists
                self._save_section_if_valid(sections, current_section, current_content)

                # Start new section
                current_section = match.group(2).strip()
                current_content = []
            elif current_section:
                # Add to current section content only if we have a current section
                current_content.append(line)

        # Save last section
        self._save_section_if_valid(sections, current_section, current_content)

        return sections

    def _save_section_if_valid(
        self,
        sections: list[tuple[str, str]],
        section_name: str | None,
        content_lines: list[str],
    ) -> None:
        """Save section to list if it exists and meets minimum length.

        Args:
            sections: List to append valid sections to
            section_name: Name of current section, or None
            content_lines: Lines of content for the section
        """
        if not section_name or not content_lines:
            return

        section_text = "\n".join(content_lines).strip()
        if len(section_text) >= self.min_length:
            sections.append((section_name, section_text))

    def find_exact_duplicates(
        self, all_sections: dict[str, list[tuple[str, str]]]
    ) -> list[DuplicateEntry]:
        """
        Find sections with identical content.

        Args:
            all_sections: Dict mapping file names to their sections

        Returns:
            List of exact duplicate entries
        """
        hash_map = self._build_content_hash_map(all_sections)
        return self._extract_duplicates_from_hash_map(hash_map)

    def _build_content_hash_map(
        self, all_sections: dict[str, list[tuple[str, str]]]
    ) -> dict[str, list[HashMapEntry]]:
        """Build hash map of content to sections."""
        hash_map: dict[str, list[HashMapEntry]] = {}

        for file_name, sections in all_sections.items():
            for section_name, content in sections:
                content_hash = hashlib.sha256(
                    self.normalize_content(content).encode()
                ).hexdigest()

                if content_hash not in hash_map:
                    hash_map[content_hash] = []

                hash_map[content_hash].append(
                    HashMapEntry(file=file_name, section=section_name, content=content)
                )

        return hash_map

    def _extract_duplicates_from_hash_map(
        self, hash_map: dict[str, list[HashMapEntry]]
    ) -> list[DuplicateEntry]:
        """Extract duplicate pairs from hash map."""
        from itertools import combinations

        # ACCEPTABLE PATTERN: Stateful accumulation of duplicate entries
        # This is inherent to the algorithm - we must accumulate duplicate pairs
        # as we discover them during hash map traversal.
        # Pre-calculation is not possible as results depend on hash map contents.
        duplicates: list[DuplicateEntry] = []

        for _content_hash, entries in hash_map.items():
            if len(entries) > 1:
                # Use itertools.combinations for cleaner O(n²) pairwise comparison
                duplicates.extend(
                    self._create_duplicate_entry(entry1, entry2)
                    for entry1, entry2 in combinations(entries, 2)
                )

        return duplicates

    def _create_duplicate_entry(
        self, entry1: HashMapEntry, entry2: HashMapEntry
    ) -> DuplicateEntry:
        """Create duplicate entry for a pair."""
        file1 = entry1.file
        section1 = entry1.section
        file2 = entry2.file
        section2 = entry2.section

        return DuplicateEntry(
            file1=file1,
            section1=section1,
            file2=file2,
            section2=section2,
            similarity=1.0,
            type="exact",
            suggestion=self.generate_refactoring_suggestion(
                file1, section1, file2, section2
            ),
        )

    def find_similar_content(
        self, all_sections: dict[str, list[tuple[str, str]]]
    ) -> list[DuplicateEntry]:
        """
        Find sections with high similarity scores using hash-based grouping.

        Performance: O(n) for grouping + O(k²) for comparing groups where k << n

        Args:
            all_sections: Dict mapping file names to their sections

        Returns:
            List of similar content entries
        """
        signature_groups = self._build_signature_groups(all_sections)
        similar = self._compare_within_groups(signature_groups)
        similar.sort(key=lambda x: x.similarity, reverse=True)
        return similar

    def _build_signature_groups(
        self, all_sections: dict[str, list[tuple[str, str]]]
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Build content signature groups for efficient comparison."""
        signature_groups: dict[str, list[tuple[str, str, str]]] = {}

        for file_name, sections in all_sections.items():
            for section_name, content in sections:
                signature = self._compute_content_signature(content)

                if signature not in signature_groups:
                    signature_groups[signature] = []

                signature_groups[signature].append((file_name, section_name, content))

        return signature_groups

    def _compare_within_groups(
        self, signature_groups: dict[str, list[tuple[str, str, str]]]
    ) -> list[DuplicateEntry]:
        """Compare sections within signature groups."""
        from itertools import combinations

        # ACCEPTABLE PATTERN: Stateful accumulation of similar content entries
        # This is inherent to the algorithm - we must accumulate similar pairs
        # as we discover them during signature group comparison.
        # Pre-calculation is not possible as similarity scores depend on pairwise comparisons.
        similar: list[DuplicateEntry] = [
            DuplicateEntry(
                file1=file1,
                section1=section1_name,
                file2=file2,
                section2=section2_name,
                similarity=similarity,
                type="similar",
                suggestion=self.generate_refactoring_suggestion(
                    file1, section1_name, file2, section2_name
                ),
            )
            for group_sections in signature_groups.values()
            if len(group_sections) > 1
            for (file1, section1_name, content1), (
                file2,
                section2_name,
                content2,
            ) in combinations(group_sections, 2)
            if self.threshold
            <= (similarity := self.compare_sections(content1, content2))
            < 1.0
        ]

        return similar

    def _compute_content_signature(self, content: str) -> str:
        """
        Compute a fast signature for content grouping.

        Similar content will have the same signature, allowing us to
        only compare within signature groups instead of all pairs.

        Uses loose bucketing to ensure similar content is grouped together.
        Strategy: Group by length/word count categories and first few words.

        Args:
            content: Content to compute signature for

        Returns:
            Content signature string
        """
        normalized = self.normalize_content(content)

        # Create signature from:
        # 1. Length bucket (wider buckets: 0-200, 200-500, 500-1000, 1000+)
        length_bucket = min(len(normalized) // 200, 5)

        # 2. Word count bucket (wider buckets: 0-20, 20-50, 50+)
        words = normalized.split()
        word_count = len(words)
        word_bucket = min(word_count // 20, 2)

        # 3. First 3-5 words (instead of character prefix)
        # This is more semantic and allows variations in later words
        first_words = " ".join(words[:3]) if len(words) >= 3 else " ".join(words)

        return f"{length_bucket}:{word_bucket}:{first_words}"

    def normalize_content(self, content: str) -> str:
        """
        Normalize content for comparison.

        Args:
            content: Content to normalize

        Returns:
            Normalized content
        """
        # Convert to lowercase
        normalized = content.lower()

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Remove punctuation (but keep some meaningful chars)
        normalized = re.sub(r"[^\w\s-]", "", normalized)

        return normalized.strip()

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using multiple algorithms.

        Algorithm: Hybrid similarity scoring combining SequenceMatcher and Jaccard.
        Purpose: Balance character-level precision (SequenceMatcher) with token-level recall (Jaccard).
        Complexity: O(n×m) time for SequenceMatcher, O(n+m) for Jaccard where n,m are text lengths.
        Rationale: SequenceMatcher catches reordering, Jaccard catches synonym/paraphrase variations.
                  Averaging reduces false positives from either algorithm alone.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Average similarity score 0.0-1.0

        Example:
            >>> detector = DuplicationDetector()
            >>> detector.calculate_similarity("hello world", "hello there")
            0.65
        """
        scores: list[float] = []

        # SequenceMatcher: Gestalt pattern matching for character-level similarity
        # Catches word reordering and minor variations efficiently
        seq_score = difflib.SequenceMatcher(None, text1, text2).ratio()
        scores.append(seq_score)

        # Jaccard similarity: Token-based set comparison
        # More robust to word order changes and synonyms
        jaccard_score = self.jaccard_similarity(text1, text2)
        scores.append(jaccard_score)

        # Average the scores to balance both approaches
        return sum(scores) / len(scores)

    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate Jaccard similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Jaccard similarity 0.0-1.0
        """
        # Tokenize
        tokens1 = set(text1.split())
        tokens2 = set(text2.split())

        # Calculate Jaccard
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))

        return intersection / union if union > 0 else 0.0

    def generate_refactoring_suggestion(
        self, file1: str, section1: str, file2: str, section2: str
    ) -> str:
        """
        Generate suggestion for eliminating duplication.

        Args:
            file1: First file name
            section1: First section name
            file2: Second file name
            section2: Second section name

        Returns:
            Refactoring suggestion string
        """
        # Determine which file should be the source
        # Prefer files that appear earlier in typical hierarchy
        hierarchy = [
            "memorybankinstructions.md",
            "projectBrief.md",
            "productContext.md",
            "systemPatterns.md",
            "techContext.md",
            "activeContext.md",
            "progress.md",
        ]

        source_file = file1
        source_section = section1
        target_file = file2
        target_section = section2

        # Swap if file2 comes before file1 in hierarchy
        if file2 in hierarchy and file1 in hierarchy:
            if hierarchy.index(file2) < hierarchy.index(file1):
                source_file, target_file = target_file, source_file
                source_section, target_section = target_section, source_section

        return (
            f"Consider using transclusion in '{target_file}' section '{target_section}': "
            f"{{{{include: {source_file}#{source_section}}}}}"
        )
