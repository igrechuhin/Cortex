"""
Rules Merger for MCP Memory Bank.

This module handles merging of shared and local rules with conflict resolution
and priority-based strategies.
"""

from typing import cast

from cortex.core.models import ModelDict

from .models import RuleMetadataEntry, RulesManifestModel


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
        shared_rules: list[ModelDict],
        local_rules: list[ModelDict],
        priority: str = "local_overrides_shared",
    ) -> list[ModelDict]:
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
        shared_rules: list[ModelDict],
        local_rules: list[ModelDict],
    ) -> list[ModelDict]:
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
        shared_rules: list[ModelDict],
        local_rules: list[ModelDict],
    ) -> list[ModelDict]:
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

    def _get_priority(self, r: ModelDict) -> int:
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
        manifest: RulesManifestModel,
        category: str,
        filename: str,
        metadata: ModelDict,
    ) -> RulesManifestModel:
        """
        Add a rule entry to the manifest.

        Args:
            manifest: Manifest model
            category: Category name
            filename: Rule filename
            metadata: Rule metadata (priority, keywords, etc.)

        Returns:
            Updated manifest model
        """

        # Ensure category exists
        if category not in manifest.categories:
            from .models import CategoryInfo

            manifest.categories[category] = CategoryInfo()

        category_info = manifest.categories[category]

        # Create rule entry
        priority_value = metadata.get("priority", 50)
        keywords_value = metadata.get("keywords", [])
        description_value = metadata.get("description", "")

        rule_entry = RuleMetadataEntry(
            file=filename,
            priority=(
                int(priority_value) if isinstance(priority_value, (int, float)) else 50
            ),
            keywords=(
                cast(list[str], keywords_value)
                if isinstance(keywords_value, list)
                else []
            ),
            description=str(description_value) if description_value is not None else "",
        )

        category_info.rules.append(rule_entry)

        return manifest

    def _get_or_create_categories(self, manifest: ModelDict) -> ModelDict:
        """Get or create categories dict in manifest.

        Args:
            manifest: Manifest dictionary

        Returns:
            Categories dictionary
        """
        categories_raw = manifest.get("categories", {})
        if not isinstance(categories_raw, dict):
            categories: ModelDict = {}
            manifest["categories"] = categories
            return categories
        return cast(ModelDict, categories_raw)

    def _ensure_category_exists(self, categories: ModelDict, category: str) -> None:
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

    def _get_or_create_rules_list(self, category_entry: ModelDict) -> list[ModelDict]:
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
        return cast(list[ModelDict], rules_list_value_raw)
