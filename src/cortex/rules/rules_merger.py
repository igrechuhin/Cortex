"""
Rules Merger for MCP Memory Bank.

This module handles merging of shared and local rules with conflict resolution
and priority-based strategies.
"""

from datetime import datetime
from typing import cast


class RulesMerger:
    """
    Merge shared and local rules with priority strategies.

    Features:
    - Local overrides shared strategy
    - Shared overrides local strategy
    - Priority-based sorting
    - Conflict detection and resolution
    """

    async def merge_rules(
        self,
        shared_rules: list[dict[str, object]],
        local_rules: list[dict[str, object]],
        priority: str = "local_overrides_shared",
    ) -> list[dict[str, object]]:
        """
        Merge shared and local rules based on priority strategy.

        Args:
            shared_rules: Rules from shared repository
            local_rules: Rules from local project
            priority: "local_overrides_shared" or "shared_overrides_local"

        Returns:
            Merged list of rules
        """
        if priority == "local_overrides_shared":
            merged = self._merge_local_overrides_shared(shared_rules, local_rules)
        else:
            merged = self._merge_shared_overrides_local(shared_rules, local_rules)

        merged.sort(key=self._get_priority, reverse=True)
        return merged

    def _merge_local_overrides_shared(
        self,
        shared_rules: list[dict[str, object]],
        local_rules: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Merge with local rules overriding shared rules.

        Args:
            shared_rules: Rules from shared repository
            local_rules: Rules from local project

        Returns:
            Merged list of rules
        """
        merged = shared_rules.copy()
        shared_files = {r["file"]: i for i, r in enumerate(shared_rules)}

        for local_rule in local_rules:
            if local_rule["file"] in shared_files:
                idx = shared_files[local_rule["file"]]
                merged[idx] = local_rule
            else:
                merged.append(local_rule)

        return merged

    def _merge_shared_overrides_local(
        self,
        shared_rules: list[dict[str, object]],
        local_rules: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Merge with shared rules overriding local rules.

        Args:
            shared_rules: Rules from shared repository
            local_rules: Rules from local project

        Returns:
            Merged list of rules
        """
        merged = local_rules.copy()
        local_files = {r["file"]: i for i, r in enumerate(local_rules)}

        for shared_rule in shared_rules:
            if shared_rule["file"] in local_files:
                idx = local_files[shared_rule["file"]]
                merged[idx] = shared_rule
            else:
                merged.append(shared_rule)

        return merged

    def _get_priority(self, r: dict[str, object]) -> int:
        """Extract priority from rule dict.

        Args:
            r: Rule dictionary

        Returns:
            Priority value (default 50)
        """
        priority = r.get("priority", 50)
        return int(priority) if isinstance(priority, (int, float)) else 50

    def add_rule_to_manifest(
        self,
        manifest: dict[str, object],
        category: str,
        filename: str,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        """
        Add a rule entry to the manifest.

        Args:
            manifest: Manifest dictionary
            category: Category name
            filename: Rule filename
            metadata: Rule metadata (priority, keywords, etc.)

        Returns:
            Updated manifest
        """
        categories = self._get_or_create_categories(manifest)
        self._ensure_category_exists(categories, category)

        category_entry = cast(dict[str, object], categories.get(category, {}))
        rules_list = self._get_or_create_rules_list(category_entry)

        rule_entry = {
            "file": filename,
            "priority": metadata.get("priority", 50),
            "keywords": metadata.get("keywords", []),
            "applies_to": metadata.get("applies_to", ["*"]),
        }

        rules_list.append(rule_entry)
        manifest["last_updated"] = datetime.now().isoformat()

        return manifest

    def _get_or_create_categories(
        self, manifest: dict[str, object]
    ) -> dict[str, object]:
        """Get or create categories dict in manifest.

        Args:
            manifest: Manifest dictionary

        Returns:
            Categories dictionary
        """
        categories_raw = manifest.get("categories", {})
        if not isinstance(categories_raw, dict):
            categories: dict[str, object] = {}
            manifest["categories"] = categories
            return categories
        return cast(dict[str, object], categories_raw)

    def _ensure_category_exists(
        self, categories: dict[str, object], category: str
    ) -> None:
        """Ensure category exists in categories dict.

        Args:
            categories: Categories dictionary
            category: Category name
        """
        if category not in categories:
            categories[category] = {
                "description": f"{category} rules",
                "always_include": False,
                "rules": [],
            }

    def _get_or_create_rules_list(
        self, category_entry: dict[str, object]
    ) -> list[dict[str, object]]:
        """Get or create rules list in category entry.

        Args:
            category_entry: Category entry dictionary

        Returns:
            Rules list
        """
        rules_list_value_raw = category_entry.get("rules", [])
        if not isinstance(rules_list_value_raw, list):
            rules_list_value_raw = []
            category_entry["rules"] = rules_list_value_raw
        return cast(list[dict[str, object]], rules_list_value_raw)
