"""
Reorganization Analyzer for MCP Memory Bank.

This module analyzes the current Memory Bank structure to identify issues
and determine if reorganization is needed.
"""

from pathlib import Path
from typing import cast

from cortex.core.models import JsonValue, ModelDict


class ReorganizationAnalyzer:
    """
    Analyzes Memory Bank structure to identify reorganization needs.

    Examines:
    - File organization and categories
    - Dependency depth and hub files
    - Structural complexity and orphaned files
    """

    def __init__(
        self,
        memory_bank_path: Path,
        max_dependency_depth: int = 5,
        enable_categories: bool = True,
    ):
        """
        Initialize the reorganization analyzer.

        Args:
            memory_bank_path: Path to Memory Bank directory
            max_dependency_depth: Maximum acceptable dependency depth
            enable_categories: Whether to suggest category-based organization
        """
        self.memory_bank_path = memory_bank_path
        self.max_dependency_depth = max_dependency_depth
        self.enable_categories = enable_categories

    async def analyze_current_structure(
        self, structure_data: ModelDict, dependency_graph: ModelDict
    ) -> ModelDict:
        """
        Analyze current Memory Bank structure.

        Args:
            structure_data: Structure analysis results
            dependency_graph: Dependency graph data

        Returns:
            Dictionary containing structure analysis
        """
        files = await self.get_all_markdown_files()
        structure = self._build_base_structure(files)
        self._apply_structure_data(structure, structure_data)
        self._apply_dependency_data(structure, dependency_graph)
        inferred = self.infer_categories(files)
        categories_json: dict[str, JsonValue] = {
            category: cast(JsonValue, cast(list[JsonValue], file_list))
            for category, file_list in inferred.items()
        }
        structure["categories"] = categories_json
        return structure

    async def get_all_markdown_files(self) -> list[str]:
        """
        Get all markdown files in Memory Bank.

        Returns:
            List of file paths
        """
        files: list[str] = []
        if self.memory_bank_path.exists():
            for file_path in self.memory_bank_path.rglob("*.md"):
                if file_path.is_file():
                    files.append(str(file_path))
        return files

    def infer_categories(self, files: list[str]) -> dict[str, list[str]]:
        """
        Infer categories from filenames.

        Args:
            files: List of file paths

        Returns:
            Dictionary mapping categories to file lists
        """
        categories: dict[str, list[str]] = {
            "context": [],
            "technical": [],
            "progress": [],
            "planning": [],
            "reference": [],
            "uncategorized": [],
        }

        for file_path in files:
            category = self._categorize_file(file_path)
            categories[category].append(file_path)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def needs_reorganization(
        self, current_structure: ModelDict, optimize_for: str
    ) -> tuple[bool, list[str]]:
        """
        Determine if reorganization is needed.

        Args:
            current_structure: Current structure data
            optimize_for: Optimization goal

        Returns:
            Tuple of (needs_reorg, reasons)
        """
        reasons: list[str] = []

        if optimize_for == "dependency_depth":
            self._check_dependency_depth(current_structure, reasons)
        elif optimize_for == "category_based":
            self._check_category_based(current_structure, reasons)
        elif optimize_for == "complexity":
            self._check_complexity(current_structure, reasons)

        return len(reasons) > 0, reasons

    def _build_base_structure(self, files: list[str]) -> ModelDict:
        """
        Build base structure dictionary.

        Args:
            files: List of markdown files

        Returns:
            Base structure dictionary
        """
        files_json = cast(list[JsonValue], files)
        return {
            "total_files": len(files),
            "files": files_json,
            "organization": "flat",
            "categories": cast(dict[str, JsonValue], {}),
            "dependency_depth": 0,
            "orphaned_files": cast(list[JsonValue], []),
            "hub_files": cast(list[JsonValue], []),
            "complexity_score": 0,
        }

    def _apply_structure_data(
        self, structure: ModelDict, structure_data: ModelDict | None
    ) -> None:
        """
        Apply structure data to structure dictionary.

        Args:
            structure: Structure dictionary to update
            structure_data: Structure data to apply
        """
        if not structure_data:
            return

        extracted_data = self._extract_structure_data_fields(structure_data)
        self._update_structure_with_data(structure, extracted_data)

    def _apply_dependency_data(
        self, structure: ModelDict, dependency_graph: ModelDict | None
    ) -> None:
        """
        Apply dependency data to structure dictionary.

        Args:
            structure: Structure dictionary to update
            dependency_graph: Dependency graph data
        """
        if not dependency_graph:
            return

        dependencies_raw = dependency_graph.get("dependencies", {})
        dependencies = (
            cast(ModelDict, dependencies_raw)
            if isinstance(dependencies_raw, dict)
            else {}
        )

        hub_files: list[str] = []
        for file, deps in dependencies.items():
            deps_dict = cast(ModelDict, deps) if isinstance(deps, dict) else {}
            dependents = cast(list[str], deps_dict.get("dependents", []))
            if len(dependents) > 3:
                hub_files.append(str(file))

        structure["hub_files"] = cast(list[JsonValue], hub_files)

    def _categorize_file(self, file_path: str) -> str:
        """
        Categorize a single file based on filename keywords.

        Args:
            file_path: Path to file

        Returns:
            Category name
        """
        filename = Path(file_path).stem.lower()

        # Category keyword mappings (order matters - most specific first)
        category_keywords = {
            "context": ["context", "active", "system"],
            "technical": ["tech", "architecture", "design"],
            "progress": ["progress", "status", "changelog"],
            "planning": ["plan", "roadmap", "brief"],
            "reference": ["api", "reference", "docs"],
        }

        # Check each category's keywords
        for category, keywords in category_keywords.items():
            if any(keyword in filename for keyword in keywords):
                return category

        return "uncategorized"

    def _check_dependency_depth(
        self, current_structure: ModelDict, reasons: list[str]
    ) -> None:
        """
        Check if dependency depth exceeds maximum.

        Args:
            current_structure: Current structure data
            reasons: List to append reasons to
        """
        depth_raw = current_structure.get("dependency_depth", 0)
        depth = int(depth_raw) if isinstance(depth_raw, (int, float)) else 0
        if depth > self.max_dependency_depth:
            reasons.append(f"Dependency depth ({depth}) exceeds recommended maximum")

    def _check_category_based(
        self, current_structure: ModelDict, reasons: list[str]
    ) -> None:
        """
        Check category-based organization issues.

        Args:
            current_structure: Current structure data
            reasons: List to append reasons to
        """
        if current_structure.get("organization") == "flat":
            total_files_raw = current_structure.get("total_files", 0)
            total_files = (
                int(total_files_raw) if isinstance(total_files_raw, (int, float)) else 0
            )
            if total_files > 7:
                reasons.append(
                    "Flat structure with many files could benefit from categorization"
                )

        categories_raw = current_structure.get("categories", {})
        categories = (
            cast(ModelDict, categories_raw) if isinstance(categories_raw, dict) else {}
        )
        uncategorized_raw = categories.get("uncategorized", [])
        uncategorized: list[str] = (
            cast(list[str], uncategorized_raw)
            if isinstance(uncategorized_raw, list)
            else []
        )
        if len(uncategorized) > 3:
            reasons.append(f"{len(uncategorized)} files lack clear categorization")

    def _check_complexity(
        self, current_structure: ModelDict, reasons: list[str]
    ) -> None:
        """
        Check complexity-related issues.

        Args:
            current_structure: Current structure data
            reasons: List to append reasons to
        """
        complexity_raw = current_structure.get("complexity_score", 0)
        complexity = (
            float(complexity_raw) if isinstance(complexity_raw, (int, float)) else 0.0
        )
        if complexity > 0.7:
            reasons.append(f"High structural complexity score ({complexity:.2f})")

        orphaned_raw = current_structure.get("orphaned_files", [])
        orphaned = (
            cast(list[str], orphaned_raw) if isinstance(orphaned_raw, list) else []
        )
        if len(orphaned) > 2:
            reasons.append(f"{len(orphaned)} orphaned files need integration")

    def _extract_structure_data_fields(self, structure_data: ModelDict) -> ModelDict:
        """
        Extract fields from structure data.

        Args:
            structure_data: Structure data dictionary

        Returns:
            Extracted fields dictionary
        """
        organization_raw = structure_data.get("organization", "flat")
        org_type = (
            str(organization_raw) if isinstance(organization_raw, str) else "flat"
        )

        dep_depth_raw = structure_data.get("dependency_depth", 0)
        dep_depth = int(dep_depth_raw) if isinstance(dep_depth_raw, (int, float)) else 0

        orphaned_raw = structure_data.get("orphaned_files", [])
        orphaned = (
            cast(list[str], orphaned_raw) if isinstance(orphaned_raw, list) else []
        )
        orphaned_json = cast(list[JsonValue], orphaned)

        complexity_raw = structure_data.get("complexity_score", 0.0)
        complexity_score = (
            float(complexity_raw) if isinstance(complexity_raw, (int, float)) else 0.0
        )

        return {
            "org_type": org_type,
            "dep_depth": dep_depth,
            "orphaned": orphaned_json,
            "complexity_score": complexity_score,
        }

    def _update_structure_with_data(
        self, structure: ModelDict, extracted_data: ModelDict
    ) -> None:
        """
        Update structure dictionary with extracted data.

        Args:
            structure: Structure dictionary to update
            extracted_data: Extracted data to apply
        """
        org_type = extracted_data.get("org_type", "flat")
        dep_depth = extracted_data.get("dep_depth", 0)
        orphaned = extracted_data.get("orphaned", [])
        complexity_score = extracted_data.get("complexity_score", 0)

        structure["organization"] = str(org_type) if org_type else "flat"
        structure["dependency_depth"] = (
            int(dep_depth) if isinstance(dep_depth, (int, float)) else 0
        )
        orphaned_files: list[str] = (
            [
                str(item)
                for item in cast(list[JsonValue], orphaned)
                if isinstance(item, str)
            ]
            if isinstance(orphaned, list)
            else []
        )
        structure["orphaned_files"] = cast(list[JsonValue], orphaned_files)
        structure["complexity_score"] = (
            float(complexity_score)
            if isinstance(complexity_score, (int, float))
            else 0.0
        )
