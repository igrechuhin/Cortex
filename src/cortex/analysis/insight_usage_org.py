"""Usage and Organization Insight Generators.

Generate insights from usage patterns and file organization.
"""

from cortex.core.models import FileOrganizationResult, FileSizeEntry

from .insight_types import InsightDict
from .models import AntiPatternInfo, CoAccessPattern
from .pattern_analyzer import PatternAnalyzer, UnusedFileEntry
from .structure_analyzer import StructureAnalyzer


class UsageOrganizationInsights:
    """Generate usage and organization insights."""

    def __init__(
        self,
        pattern_analyzer: PatternAnalyzer,
        structure_analyzer: StructureAnalyzer,
    ) -> None:
        """
        Initialize usage and organization insight generators.

        Args:
            pattern_analyzer: Pattern analyzer instance
            structure_analyzer: Structure analyzer instance
        """
        self.pattern_analyzer: PatternAnalyzer = pattern_analyzer
        self.structure_analyzer: StructureAnalyzer = structure_analyzer

    async def generate_usage_insights(self) -> list[InsightDict]:
        """Generate insights from usage patterns."""
        insights: list[InsightDict] = []

        unused_insight = await self._analyze_unused_files()
        if unused_insight:
            insights.append(unused_insight)

        co_access_insight = await self._analyze_co_access_patterns()
        if co_access_insight:
            insights.append(co_access_insight)

        return insights

    async def _analyze_unused_files(self) -> InsightDict | None:
        """Analyze unused files and generate insight.

        Returns:
            Insight dictionary or None if no unused files found
        """
        unused_files: list[UnusedFileEntry] = (
            await self.pattern_analyzer.get_unused_files(time_range_days=60)
        )

        if len(unused_files) < 3:
            return None

        stale_count, never_accessed = self._count_unused_file_statuses(unused_files)

        return self._create_unused_files_insight(
            unused_files, stale_count, never_accessed
        )

    def _create_unused_files_insight(
        self,
        unused_files: list[UnusedFileEntry],
        stale_count: int,
        never_accessed: int,
    ) -> InsightDict:
        """Create insight for unused files."""
        evidence = self._build_unused_files_evidence(
            unused_files, stale_count, never_accessed
        )
        return InsightDict.model_validate(
            {
                "id": "unused_files",
                "category": "usage",
                "title": f"Found {len(unused_files)} unused or stale files",
                "description": (
                    f"{stale_count} files haven't been accessed in 60+ days, "
                    f"{never_accessed} have never been accessed"
                ),
                "impact_score": 0.7,
                "severity": "medium",
                "evidence": evidence,
                "recommendations": self._get_unused_files_recommendations(),
                "estimated_token_savings": len(unused_files) * 500,
            }
        )

    def _build_unused_files_evidence(
        self,
        unused_files: list[UnusedFileEntry],
        stale_count: int,
        never_accessed: int,
    ) -> dict[str, object]:
        """Build evidence dict for unused files insight."""
        return {
            "unused_count": len(unused_files),
            "stale_count": stale_count,
            "never_accessed_count": never_accessed,
            "example_files": [f.model_dump(mode="json") for f in unused_files[:3]],
        }

    def _get_unused_files_recommendations(self) -> list[str]:
        """Get recommendations for unused files."""
        return [
            "Review unused files and consider archiving or removing them",
            "Add links from active files if these should be used",
            "Update content if files are outdated",
        ]

    def _count_unused_file_statuses(
        self, unused_files: list[UnusedFileEntry]
    ) -> tuple[int, int]:
        """Count unused file statuses.

        Args:
            unused_files: List of unused file entries

        Returns:
            Tuple of (stale_count, never_accessed_count)
        """
        stale_count = len([f for f in unused_files if f.status == "stale"])
        never_accessed = len([f for f in unused_files if f.status == "never_accessed"])
        return (stale_count, never_accessed)

    async def _analyze_co_access_patterns(self) -> InsightDict | None:
        """Analyze co-access patterns and generate insight.

        Returns:
            Insight dictionary or None if no patterns found
        """
        co_access: list[CoAccessPattern] = (
            await self.pattern_analyzer.get_co_access_patterns(min_co_access_count=5)
        )

        if len(co_access) < 3:
            return None

        return InsightDict.model_validate(
            {
                "id": "co_access_patterns",
                "category": "usage",
                "title": f"Found {len(co_access)} frequently co-accessed file pairs",
                "description": (
                    "These files are often accessed together and might "
                    "benefit from consolidation"
                ),
                "impact_score": 0.6,
                "severity": "low",
                "evidence": {
                    "pattern_count": len(co_access),
                    "example_patterns": [
                        p.model_dump(mode="json") for p in co_access[:5]
                    ],
                },
                "recommendations": [
                    "Consider consolidating closely related files",
                    "Add cross-references between co-accessed files",
                    "Use transclusion for shared content",
                ],
                "estimated_token_savings": len(co_access) * 200,
            }
        )

    async def generate_organization_insights(self) -> list[InsightDict]:
        """Generate insights from file organization."""
        insights: list[InsightDict] = []

        org_analysis = await self.structure_analyzer.analyze_file_organization()

        if org_analysis.status == "analyzed":
            issues = org_analysis.issues or []

            if issues and any("large" in issue for issue in issues):
                large_insight = self._create_large_files_insight(org_analysis, issues)
                if large_insight:
                    insights.append(large_insight)

            if any("small" in issue for issue in issues):
                small_insight = self._create_small_files_insight(org_analysis)
                if small_insight:
                    insights.append(small_insight)

        return insights

    def _create_large_files_insight(
        self, org_analysis: FileOrganizationResult, issues: list[str]
    ) -> InsightDict | None:
        """Create insight for large files.

        Args:
            org_analysis: Organization analysis dictionary
            issues: List of issue strings

        Returns:
            Large files insight dictionary or None
        """
        large_count = self._extract_large_count(issues)
        if large_count == 0:
            return None

        largest_files = self._extract_largest_files(org_analysis)
        affected_files = self._extract_affected_files(largest_files)

        return self._build_large_files_insight_dict(
            large_count, largest_files, affected_files
        )

    def _extract_large_count(self, issues: list[str]) -> int:
        """Extract large file count from issues."""
        if not issues:
            return 0
        try:
            return int(issues[0].split()[0])
        except (ValueError, IndexError):
            return 0

    def _build_large_files_insight_dict(
        self,
        large_count: int,
        largest_files: list[FileSizeEntry],
        affected_files: list[str],
    ) -> InsightDict:
        """Build large files insight dictionary."""
        largest_files_dict = self._convert_file_size_entries_to_dict(largest_files)
        evidence = {
            "large_file_count": large_count,
            "largest_files": largest_files_dict,
        }
        return InsightDict.model_validate(
            {
                "id": "large_files",
                "category": "organization",
                "title": f"{large_count} files are very large",
                "description": (
                    "Large files may benefit from being split into "
                    "smaller, focused files"
                ),
                "impact_score": 0.75,
                "severity": "medium",
                "evidence": evidence,
                "affected_files": affected_files,
                "recommendations": self._get_large_files_recommendations(),
                "estimated_token_savings": large_count * 1000,
            }
        )

    def _convert_file_size_entries_to_dict(
        self, files: list[FileSizeEntry]
    ) -> list[dict[str, object]]:
        """Convert FileSizeEntry list to dict list."""
        return [
            {"file": f.file, "size_bytes": f.size_bytes, "tokens": f.tokens}
            for f in files
        ]

    def _get_large_files_recommendations(self) -> list[str]:
        """Get recommendations for large files."""
        return [
            "Split large files by topic or section",
            "Extract reusable content into separate files",
            "Use transclusion to compose split files",
        ]

    def _extract_largest_files(
        self, org_analysis: FileOrganizationResult
    ) -> list[FileSizeEntry]:
        """Extract largest files from organization analysis.

        Args:
            org_analysis: Organization analysis result

        Returns:
            List of largest file info models
        """
        return org_analysis.largest_files[:3] if org_analysis.largest_files else []

    def _extract_affected_files(self, largest_files: list[FileSizeEntry]) -> list[str]:
        """Extract affected file names from largest files.

        Args:
            largest_files: List of largest file info models

        Returns:
            List of affected file names
        """
        return [file_info.file for file_info in largest_files if file_info.file]

    def _create_small_files_insight(
        self, org_analysis: FileOrganizationResult
    ) -> InsightDict | None:
        """Create insight for small files.

        Args:
            org_analysis: Organization analysis result

        Returns:
            Small files insight dictionary or None
        """
        smallest_files = org_analysis.smallest_files or []
        small_count = self._count_very_small_files(smallest_files)

        if small_count < 3:
            return None

        smallest_files_slice = smallest_files[:3]
        smallest_files_dict = self._convert_file_size_entries_to_dict(
            smallest_files_slice
        )
        evidence = {
            "small_file_count": small_count,
            "smallest_files": smallest_files_dict,
        }
        return InsightDict.model_validate(
            {
                "id": "small_files",
                "category": "organization",
                "title": f"{small_count} files are very small",
                "description": (
                    "Very small files might be better consolidated into larger files"
                ),
                "impact_score": 0.5,
                "severity": "low",
                "evidence": evidence,
                "recommendations": self._get_small_files_recommendations(),
                "estimated_token_savings": small_count * 50,
            }
        )

    def _get_small_files_recommendations(self) -> list[str]:
        """Get recommendations for small files."""
        return [
            "Consider consolidating related small files",
            "Merge small files with their parent topics",
            "Evaluate if content justifies separate files",
        ]

    def _count_very_small_files(self, smallest_files: list[FileSizeEntry]) -> int:
        """Count files smaller than 500 bytes.

        Args:
            smallest_files: List of smallest file info models

        Returns:
            Count of very small files
        """
        return sum(1 for f in smallest_files if f.size_bytes < 500)

    async def generate_redundancy_insights(self) -> list[InsightDict]:
        """Generate insights about redundant content."""
        insights: list[InsightDict] = []

        anti_patterns = await self.structure_analyzer.detect_anti_patterns()
        similar_names = self._extract_similar_filename_patterns(anti_patterns)

        if len(similar_names) >= 2:
            insights.append(self._create_similar_filenames_insight(similar_names))

        return insights

    def _extract_similar_filename_patterns(
        self, anti_patterns: list[AntiPatternInfo]
    ) -> list[AntiPatternInfo]:
        """Extract similar filename patterns from anti-patterns."""
        return [ap for ap in anti_patterns if ap.type == "similar_filenames"]

    def _create_similar_filenames_insight(
        self, similar_names: list[AntiPatternInfo]
    ) -> InsightDict:
        """Create insight for similar filenames."""
        return InsightDict.model_validate(
            {
                "id": "similar_filenames",
                "category": "redundancy",
                "title": f"Found {len(similar_names)} pairs of files with similar names",
                "description": "Similar file names may indicate duplicate or overlapping content",
                "impact_score": 0.65,
                "severity": "medium",
                "evidence": {
                    "similar_pair_count": len(similar_names),
                    "example_patterns": [
                        ap.model_dump(mode="json") for ap in similar_names[:3]
                    ],
                },
                "recommendations": [
                    "Review files with similar names for duplicate content",
                    "Consider consolidating if content overlaps",
                    "Use transclusion for shared sections",
                    "Rename files to be more distinct",
                ],
                "estimated_token_savings": len(similar_names) * 300,
            }
        )
