"""
Rules Loader for MCP Memory Bank.

This module handles loading rules from the shared rules repository,
including manifest parsing, category loading, and rule file reading.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file


class RulesLoader:
    """
    Load and parse rules from shared repository.

    Features:
    - Rules manifest parsing and validation
    - Category-based rule loading
    - Rule file reading with metadata
    - Context-aware rule filtering
    """

    def __init__(self, shared_rules_path: Path):
        """
        Initialize rules loader.

        Args:
            shared_rules_path: Path to shared rules folder
        """
        self.shared_rules_path: Path = shared_rules_path
        self.manifest: dict[str, object] | None = None
        self.manifest_cache: dict[str, object] | None = None

    async def load_manifest(self) -> dict[str, object] | None:
        """
        Load and parse rules-manifest.json.

        Returns:
            Parsed manifest dict or None if not found
        """
        try:
            manifest_path = self.shared_rules_path / "rules-manifest.json"

            if not manifest_path.exists():
                self.manifest = None
                return None

            async with open_async_text_file(manifest_path, "r", "utf-8") as f:
                content = await f.read()
                manifest_data = json.loads(content)
                if manifest_data and isinstance(manifest_data, dict):
                    self.manifest = manifest_data
                    self.manifest_cache = manifest_data.copy()
                else:
                    self.manifest = None
                    self.manifest_cache = None
                return self.manifest

        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to load rules manifest: {e}")
            self.manifest = None
            return None

    def get_categories(self) -> list[str]:
        """
        Get list of available categories from manifest.

        Returns:
            List of category names
        """
        if not self.manifest:
            return []

        categories = self.manifest.get("categories")
        if isinstance(categories, dict):
            return list(cast(dict[str, object], categories).keys())

        return []

    async def load_category(self, category: str) -> list[dict[str, object]]:
        """
        Load all rules from a specific category.

        Args:
            category: Category name (e.g., "python", "generic")

        Returns:
            List of rule dicts with content and metadata
        """
        if not self.manifest:
            _ = await self.load_manifest()

        if not self.manifest:
            return []

        category_info = self._get_category_info(category)
        if not category_info:
            return []

        category_path = self.shared_rules_path / category
        if not category_path.exists():
            return []

        rules_list = self._extract_rules_list(category_info)
        return await self._load_rules_from_files(category, category_path, rules_list)

    def _get_category_info(self, category: str) -> dict[str, object] | None:
        """Get category info from manifest.

        Args:
            category: Category name

        Returns:
            Category info dict or None if not found
        """
        if not self.manifest:
            return None
        categories_raw: object = self.manifest.get("categories", {})
        if not isinstance(categories_raw, dict):
            return None
        categories: dict[str, object] = cast(dict[str, object], categories_raw)
        if category not in categories:
            return None
        category_info_raw: object = categories[category]
        if not isinstance(category_info_raw, dict):
            return None
        return cast(dict[str, object], category_info_raw)

    def _extract_rules_list(
        self, category_info: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract rules list from category info.

        Args:
            category_info: Category info dict

        Returns:
            List of rule info dicts
        """
        rules_list_value = category_info.get("rules", [])
        if not isinstance(rules_list_value, list):
            return []
        return cast(list[dict[str, object]], rules_list_value)

    async def _load_rules_from_files(
        self,
        category: str,
        category_path: Path,
        rules_list: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Load rules from files in category.

        Args:
            category: Category name
            category_path: Path to category directory
            rules_list: List of rule info dicts

        Returns:
            List of loaded rule dicts
        """
        rules: list[dict[str, object]] = []
        for rule_info in rules_list:
            rule = await self._load_single_rule_file(category, category_path, rule_info)
            if rule:
                rules.append(rule)
        return rules

    async def _load_single_rule_file(
        self,
        category: str,
        category_path: Path,
        rule_info: dict[str, object],
    ) -> dict[str, object] | None:
        """Load a single rule file."""
        rule_file_name_value = rule_info.get("file")
        if not isinstance(rule_file_name_value, str):
            return None

        rule_file = category_path / rule_file_name_value
        if not rule_file.exists():
            return None

        try:
            async with open_async_text_file(rule_file, "r", "utf-8") as f:
                content = await f.read()

            return {
                "category": category,
                "file": rule_file_name_value,
                "path": str(rule_file),
                "content": content,
                "priority": rule_info.get("priority", 50),
                "keywords": rule_info.get("keywords", []),
                "source": "shared",
            }
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to load shared rule {rule_file}: {e}")
            return None

    async def save_manifest(self, manifest: dict[str, object]) -> None:
        """
        Save manifest to rules-manifest.json.

        Args:
            manifest: Manifest data to save
        """
        manifest_path = self.shared_rules_path / "rules-manifest.json"
        async with open_async_text_file(manifest_path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(manifest, indent=2))
        self.manifest = manifest
        self.manifest_cache = manifest.copy()

    async def create_rule_file(
        self, category: str, filename: str, content: str
    ) -> Path:
        """
        Create a new rule file in the specified category.

        Args:
            category: Category name
            filename: Rule filename
            content: Rule content

        Returns:
            Path to created file
        """
        category_path = self.shared_rules_path / category
        category_path.mkdir(exist_ok=True)
        rule_path = category_path / filename

        async with open_async_text_file(rule_path, "w", "utf-8") as f:
            _ = await f.write(content)

        return rule_path

    async def update_rule_file(self, rule_path: Path, content: str) -> None:
        """
        Update an existing rule file.

        Args:
            rule_path: Path to rule file
            content: New content
        """
        async with open_async_text_file(rule_path, "w", "utf-8") as f:
            _ = await f.write(content)
