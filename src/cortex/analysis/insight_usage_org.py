"""Usage and Organization Insight Generators.

Generate insights from usage patterns and file organization.
"""

from typing import cast

from .insight_types import InsightDict
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
        return InsightDict(
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
                "evidence": {
                    "unused_count": len(unused_files),
                    "stale_count": stale_count,
                    "never_accessed_count": never_accessed,
                    "examples": unused_files[:3],
                },
                "recommendations": [
                    "Review unused files and consider archiving or removing them",
                    "Add links from active files if these should be used",
                    "Update content if files are outdated",
                ],
                "estimated_token_savings": len(unused_files) * 500,
            }
        )

    def _count_unused_file_statuses(
        self, unused_files: list[UnusedFileEntry]
    ) -> tuple[int, int]:
        """Count unused file statuses.

        Args:
            unused_files: List of unused file entries

        Returns:
            Tuple of (stale_count, never_accessed_count)
        """
        stale_count = len(
            [f for f in unused_files if str(f.get("status", "")) == "stale"]
        )
        never_accessed = len(
            [f for f in unused_files if str(f.get("status", "")) == "never_accessed"]
        )
        return (stale_count, never_accessed)

    async def _analyze_co_access_patterns(self) -> InsightDict | None:
        """Analyze co-access patterns and generate insight.

        Returns:
            Insight dictionary or None if no patterns found
        """
        co_access: list[dict[str, object]] = (
            await self.pattern_analyzer.get_co_access_patterns(min_co_access_count=5)
        )

        if len(co_access) < 3:
            return None

        return InsightDict(
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
                    "examples": co_access[:5],
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

        if str(org_analysis.get("status", "")) == "analyzed":
            issues = self._extract_issues_from_analysis(org_analysis)

            if issues and any("large" in issue for issue in issues):
                large_insight = self._create_large_files_insight(org_analysis, issues)
                if large_insight:
                    insights.append(large_insight)

            if any("small" in issue for issue in issues):
                small_insight = self._create_small_files_insight(org_analysis)
                if small_insight:
                    insights.append(small_insight)

        return insights

    def _extract_issues_from_analysis(
        self, org_analysis: dict[str, object]
    ) -> list[str]:
        """Extract issues list from organization analysis.

        Args:
            org_analysis: Organization analysis dictionary

        Returns:
            List of issue strings
        """
        issues_raw: object = org_analysis.get("issues", [])
        if isinstance(issues_raw, list):
            issues_list_raw: list[object] = cast(list[object], issues_raw)
            return [str(item) for item in issues_list_raw if isinstance(item, str)]
        return []

    def _create_large_files_insight(
        self, org_analysis: dict[str, object], issues: list[str]
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
        largest_files: list[dict[str, object]],
        affected_files: list[str],
    ) -> InsightDict:
        """Build large files insight dictionary."""
        return InsightDict(
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
                "evidence": {
                    "large_file_count": large_count,
                    "largest_files": largest_files,
                },
                "affected_files": affected_files,
                "recommendations": [
                    "Split large files by topic or section",
                    "Extract reusable content into separate files",
                    "Use transclusion to compose split files",
                ],
                "estimated_token_savings": large_count * 1000,
            }
        )

    def _extract_largest_files(
        self, org_analysis: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract largest files from organization analysis.

        Args:
            org_analysis: Organization analysis dictionary

        Returns:
            List of largest file dictionaries
        """
        largest_files_raw: object = org_analysis.get("largest_files", [])
        largest_files: list[dict[str, object]] = []
        if isinstance(largest_files_raw, list):
            largest_files_list: list[object] = cast(list[object], largest_files_raw)
            for item in largest_files_list[:3]:
                if isinstance(item, dict):
                    largest_files.append(cast(dict[str, object], item))
        return largest_files

    def _extract_affected_files(
        self, largest_files: list[dict[str, object]]
    ) -> list[str]:
        """Extract affected file names from largest files.

        Args:
            largest_files: List of largest file dictionaries

        Returns:
            List of affected file names
        """
        affected_files_list: list[str] = []
        for file_info in largest_files:
            file_name = file_info.get("file", "")
            if isinstance(file_name, str) and file_name:
                affected_files_list.append(file_name)
        return affected_files_list

    def _create_small_files_insight(
        self, org_analysis: dict[str, object]
    ) -> InsightDict | None:
        """Create insight for small files.

        Args:
            org_analysis: Organization analysis dictionary

        Returns:
            Small files insight dictionary or None
        """
        smallest_files = self._extract_smallest_files(org_analysis)
        small_count = self._count_very_small_files(smallest_files)

        if small_count < 3:
            return None

        smallest_files_slice = smallest_files[:3]
        return InsightDict(
            {
                "id": "small_files",
                "category": "organization",
                "title": f"{small_count} files are very small",
                "description": (
                    "Very small files might be better consolidated into larger files"
                ),
                "impact_score": 0.5,
                "severity": "low",
                "evidence": {
                    "small_file_count": small_count,
                    "smallest_files": smallest_files_slice,
                },
                "recommendations": [
                    "Consider consolidating related small files",
                    "Merge small files with their parent topics",
                    "Evaluate if content justifies separate files",
                ],
                "estimated_token_savings": small_count * 50,
            }
        )

    def _extract_smallest_files(
        self, org_analysis: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract smallest files from organization analysis.

        Args:
            org_analysis: Organization analysis dictionary

        Returns:
            List of smallest file dictionaries
        """
        smallest_files_raw: object = org_analysis.get("smallest_files", [])
        smallest_files: list[dict[str, object]] = []
        if isinstance(smallest_files_raw, list):
            smallest_files_list: list[object] = cast(list[object], smallest_files_raw)
            for item in smallest_files_list:
                if isinstance(item, dict):
                    smallest_files.append(cast(dict[str, object], item))
        return smallest_files

    def _count_very_small_files(self, smallest_files: list[dict[str, object]]) -> int:
        """Count files smaller than 500 bytes.

        Args:
            smallest_files: List of smallest file dictionaries

        Returns:
            Count of very small files
        """
        return sum(
            1
            for f in smallest_files
            if (
                (size_bytes := f.get("size_bytes")) is not None
                and isinstance(size_bytes, (int, float))
                and int(size_bytes) < 500
            )
        )

    async def generate_redundancy_insights(self) -> list[InsightDict]:
        """Generate insights about redundant content."""
        insights: list[InsightDict] = []

        anti_patterns = await self.structure_analyzer.detect_anti_patterns()
        similar_names = self._extract_similar_filename_patterns(anti_patterns)

        if len(similar_names) >= 2:
            insights.append(self._create_similar_filenames_insight(similar_names))

        return insights

    def _extract_similar_filename_patterns(
        self, anti_patterns: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Extract similar filename patterns from anti-patterns."""
        similar_names: list[dict[str, object]] = []
        for ap in anti_patterns:
            if str(ap.get("type", "")) == "similar_filenames":
                similar_names.append(ap)
        return similar_names

    def _create_similar_filenames_insight(
        self, similar_names: list[dict[str, object]]
    ) -> InsightDict:
        """Create insight for similar filenames."""
        return InsightDict(
            {
                "id": "similar_filenames",
                "category": "redundancy",
                "title": f"Found {len(similar_names)} pairs of files with similar names",
                "description": "Similar file names may indicate duplicate or overlapping content",
                "impact_score": 0.65,
                "severity": "medium",
                "evidence": {
                    "similar_pair_count": len(similar_names),
                    "examples": similar_names[:3],
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
