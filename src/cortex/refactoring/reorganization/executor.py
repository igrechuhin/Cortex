"""
Reorganization Executor for MCP Memory Bank.

This module generates actions and calculates impact for reorganization plans.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast


@dataclass
class ReorganizationAction:
    """Represents a single reorganization action"""

    action_type: str  # "move", "rename", "reorder", "create_category"
    source: str
    target: str
    reason: str
    dependencies_affected: list[str] = field(default_factory=lambda: list[str]())


class ReorganizationExecutor:
    """
    Generates reorganization actions and calculates their impact.

    Handles:
    - Action generation for different optimization goals
    - Impact calculation (files moved, categories created, etc.)
    - Risk and benefit identification
    """

    def __init__(self, memory_bank_path: Path):
        """
        Initialize the reorganization executor.

        Args:
            memory_bank_path: Path to Memory Bank directory
        """
        self.memory_bank_path = memory_bank_path

    async def generate_actions(
        self,
        current_structure: dict[str, object],
        proposed_structure: dict[str, object],
        optimize_for: str,
    ) -> list[ReorganizationAction]:
        """
        Generate actions to transform structure.

        Args:
            current_structure: Current structure data
            proposed_structure: Proposed structure data
            optimize_for: Optimization goal

        Returns:
            List of reorganization actions
        """
        actions: list[ReorganizationAction] = []

        if optimize_for == "category_based":
            actions.extend(self._generate_category_based_actions(proposed_structure))
        elif optimize_for == "dependency_depth":
            actions.extend(self._generate_dependency_depth_actions(proposed_structure))
        elif optimize_for == "complexity":
            actions.extend(self._generate_complexity_actions(proposed_structure))

        return actions

    def calculate_impact(
        self,
        current_structure: dict[str, object],
        proposed_structure: dict[str, object],
        actions: list[ReorganizationAction],
    ) -> dict[str, object]:
        """
        Calculate estimated impact of reorganization.

        Args:
            current_structure: Current structure data
            proposed_structure: Proposed structure data
            actions: List of reorganization actions

        Returns:
            Dictionary containing impact metrics
        """
        move_actions = [a for a in actions if a.action_type == "move"]
        create_actions = [a for a in actions if a.action_type == "create_category"]

        return {
            "files_moved": len(move_actions),
            "categories_created": len(create_actions),
            "dependency_depth_reduction": 0.3,  # Estimated
            "complexity_reduction": 0.4,
            "maintainability_improvement": 0.6,
            "navigation_improvement": 0.7,
            "estimated_effort": "medium" if len(actions) > 10 else "low",
        }

    def identify_risks(
        self, actions: list[ReorganizationAction], current_structure: dict[str, object]
    ) -> list[str]:
        """
        Identify risks of reorganization.

        Args:
            actions: List of reorganization actions
            current_structure: Current structure data

        Returns:
            List of risk descriptions
        """
        risks: list[str] = []

        move_count = len([a for a in actions if a.action_type == "move"])

        if move_count > 5:
            risks.append(f"Moving {move_count} files requires updating many links")

        if move_count > 10:
            risks.append("Large-scale reorganization may disrupt active development")

        dependency_depth_raw = current_structure.get("dependency_depth", 0)
        dependency_depth = (
            int(dependency_depth_raw)
            if isinstance(dependency_depth_raw, (int, float))
            else 0
        )
        if dependency_depth > 3:
            risks.append("Complex dependencies may break if not handled carefully")

        if not risks:
            risks.append("Low risk - straightforward reorganization")

        return risks

    def identify_benefits(
        self,
        proposed_structure: dict[str, object],
        current_structure: dict[str, object],
    ) -> list[str]:
        """
        Identify benefits of reorganization.

        Args:
            proposed_structure: Proposed structure data
            current_structure: Current structure data

        Returns:
            List of benefit descriptions
        """
        benefits: list[str] = []

        org_type = proposed_structure.get("organization")

        if org_type == "category_based":
            benefits.append("Clear categorization improves discoverability")
            benefits.append("Easier to locate relevant files by topic")
            benefits.append("Better mental model of Memory Bank structure")

        if org_type == "dependency_optimized":
            benefits.append("Reduced dependency depth improves load times")
            benefits.append("Clearer dependency flow")
            benefits.append("Easier to understand file relationships")

        if org_type == "simplified":
            benefits.append("Simplified structure reduces cognitive load")
            benefits.append("Faster navigation with fewer categories")
            benefits.append("More maintainable long-term")

        # Always add
        benefits.append("Improved overall Memory Bank organization")

        return benefits

    def _generate_category_based_actions(
        self, proposed_structure: dict[str, object]
    ) -> list[ReorganizationAction]:
        """
        Generate actions for category-based organization.

        Args:
            proposed_structure: Proposed structure with categories

        Returns:
            List of reorganization actions
        """
        actions: list[ReorganizationAction] = []
        proposed_categories = _extract_categories(proposed_structure)

        for category, files in proposed_categories.items():
            category_str = str(category)
            category_files: list[str] = (
                cast(list[str], files) if isinstance(files, list) else []
            )
            category_dir = self.memory_bank_path / category_str

            actions.append(
                _create_category_action(category_str, category_dir, "organization")
            )

            actions.extend(
                _create_move_actions(
                    category_files, category_dir, category_str, "category"
                )
            )

        return actions

    def _generate_dependency_depth_actions(
        self, proposed_structure: dict[str, object]
    ) -> list[ReorganizationAction]:
        """
        Generate actions for dependency depth optimization.

        Args:
            proposed_structure: Proposed structure with dependency order

        Returns:
            List of reorganization actions
        """
        actions: list[ReorganizationAction] = []
        proposed_order_raw = proposed_structure.get("dependency_order", [])
        proposed_order = (
            cast(list[str], proposed_order_raw)
            if isinstance(proposed_order_raw, list)
            else []
        )

        if proposed_order:
            actions.append(
                ReorganizationAction(
                    action_type="reorder",
                    source="current",
                    target="optimized",
                    reason="Optimize dependency order to reduce depth",
                    dependencies_affected=proposed_order,
                )
            )

        return actions

    def _generate_complexity_actions(
        self, proposed_structure: dict[str, object]
    ) -> list[ReorganizationAction]:
        """
        Generate actions for complexity reduction.

        Args:
            proposed_structure: Proposed structure with simplified categories

        Returns:
            List of reorganization actions
        """
        actions: list[ReorganizationAction] = []
        proposed_categories = _extract_categories(proposed_structure)

        for category, files in proposed_categories.items():
            category_str = str(category)
            simplified_files: list[str] = (
                cast(list[str], files) if isinstance(files, list) else []
            )
            category_dir = self.memory_bank_path / category_str

            actions.append(
                _create_category_action(
                    category_str, category_dir, "simplified structure"
                )
            )

            actions.extend(
                _create_move_actions(
                    simplified_files, category_dir, category_str, "simplified access"
                )
            )

        return actions


def _extract_categories(
    proposed_structure: dict[str, object],
) -> dict[str, object]:
    """
    Extract categories from proposed structure.

    Args:
        proposed_structure: Proposed structure dictionary

    Returns:
        Dictionary of categories
    """
    proposed_categories_raw = proposed_structure.get("categories", {})
    return (
        cast(dict[str, object], proposed_categories_raw)
        if isinstance(proposed_categories_raw, dict)
        else {}
    )


def _create_category_action(
    category_str: str, category_dir: Path, context: str
) -> ReorganizationAction:
    """
    Create a category creation action.

    Args:
        category_str: Category name as string
        category_dir: Category directory path
        context: Context for the reason message

    Returns:
        ReorganizationAction for creating category
    """
    return ReorganizationAction(
        action_type="create_category",
        source="",
        target=str(category_dir),
        reason=f"Create '{category_str}' category for {context}",
    )


def _create_move_actions(
    files: list[str],
    category_dir: Path,
    category_str: str,
    reason_context: str,
) -> list[ReorganizationAction]:
    """
    Create move actions for files in a category.

    Args:
        files: List of file paths to move
        category_dir: Target category directory
        category_str: Category name as string
        reason_context: Context for the reason message

    Returns:
        List of ReorganizationAction for moving files
    """
    actions: list[ReorganizationAction] = []
    for file_path in files:
        current_path = Path(file_path)
        new_path = category_dir / current_path.name

        if str(new_path) != file_path:
            actions.append(
                ReorganizationAction(
                    action_type="move",
                    source=file_path,
                    target=str(new_path),
                    reason=f"Move to '{category_str}' for {reason_context}",
                )
            )
    return actions
