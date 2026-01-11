"""
Prompts Loader for MCP Memory Bank.

This module handles loading prompts from the Synapse repository,
including manifest parsing, category loading, and prompt file reading.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file


class PromptsLoader:
    """
    Load and parse prompts from Synapse repository.

    Features:
    - Prompts manifest parsing and validation
    - Category-based prompt loading
    - Prompt file reading with metadata
    - Context-aware prompt filtering
    """

    def __init__(self, prompts_path: Path):
        """
        Initialize prompts loader.

        Args:
            prompts_path: Path to prompts folder in Synapse
        """
        self.prompts_path: Path = prompts_path
        self.manifest: dict[str, object] | None = None
        self.manifest_cache: dict[str, object] | None = None

    async def load_manifest(self) -> dict[str, object] | None:
        """
        Load and parse prompts-manifest.json.

        Returns:
            Parsed manifest dict or None if not found
        """
        try:
            manifest_path = self.prompts_path / "prompts-manifest.json"

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

            logger.warning(f"Failed to load prompts manifest: {e}")
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
        Load all prompts from a specific category.

        Args:
            category: Category name (e.g., "python", "general")

        Returns:
            List of prompt dicts with content and metadata
        """
        if not self.manifest:
            _ = await self.load_manifest()

        if not self.manifest:
            return []

        category_info = self._get_category_info(category)
        if not category_info:
            return []

        category_path = self.prompts_path / category
        if not category_path.exists():
            return []

        prompts_list = self._extract_prompts_list(category_info)
        return await self._load_prompts_from_files(
            category, category_path, prompts_list
        )

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

    def _extract_prompts_list(
        self, category_info: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract prompts list from category info.

        Args:
            category_info: Category info dict

        Returns:
            List of prompt info dicts
        """
        prompts_list_value = category_info.get("prompts", [])
        if not isinstance(prompts_list_value, list):
            return []
        return cast(list[dict[str, object]], prompts_list_value)

    async def _load_prompts_from_files(
        self,
        category: str,
        category_path: Path,
        prompts_list: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Load prompts from files in category.

        Args:
            category: Category name
            category_path: Path to category directory
            prompts_list: List of prompt info dicts

        Returns:
            List of loaded prompt dicts
        """
        prompts: list[dict[str, object]] = []
        for prompt_info in prompts_list:
            prompt = await self._load_single_prompt_file(
                category, category_path, prompt_info
            )
            if prompt:
                prompts.append(prompt)
        return prompts

    async def _load_single_prompt_file(
        self,
        category: str,
        category_path: Path,
        prompt_info: dict[str, object],
    ) -> dict[str, object] | None:
        """Load a single prompt file."""
        prompt_file_name_value = prompt_info.get("file")
        if not isinstance(prompt_file_name_value, str):
            return None

        prompt_file = category_path / prompt_file_name_value
        if not prompt_file.exists():
            return None

        try:
            async with open_async_text_file(prompt_file, "r", "utf-8") as f:
                content = await f.read()

            return {
                "category": category,
                "file": prompt_file_name_value,
                "path": str(prompt_file),
                "content": content,
                "name": prompt_info.get("name", prompt_file_name_value),
                "description": prompt_info.get("description", ""),
                "keywords": prompt_info.get("keywords", []),
                "source": "synapse",
            }
        except Exception as e:
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to load prompt {prompt_file}: {e}")
            return None

    async def save_manifest(self, manifest: dict[str, object]) -> None:
        """
        Save manifest to prompts-manifest.json.

        Args:
            manifest: Manifest data to save
        """
        manifest_path = self.prompts_path / "prompts-manifest.json"
        async with open_async_text_file(manifest_path, "w", "utf-8") as f:
            _ = await f.write(json.dumps(manifest, indent=2))
        self.manifest = manifest
        self.manifest_cache = manifest.copy()

    async def create_prompt_file(
        self, category: str, filename: str, content: str
    ) -> Path:
        """
        Create a new prompt file in the specified category.

        Args:
            category: Category name
            filename: Prompt filename
            content: Prompt content

        Returns:
            Path to created file
        """
        category_path = self.prompts_path / category
        category_path.mkdir(exist_ok=True)
        prompt_path = category_path / filename

        async with open_async_text_file(prompt_path, "w", "utf-8") as f:
            _ = await f.write(content)

        return prompt_path

    async def update_prompt_file(self, prompt_path: Path, content: str) -> None:
        """
        Update an existing prompt file.

        Args:
            prompt_path: Path to prompt file
            content: New content
        """
        async with open_async_text_file(prompt_path, "w", "utf-8") as f:
            _ = await f.write(content)

    async def get_all_prompts(self) -> list[dict[str, object]]:
        """
        Load all prompts from all categories.

        Returns:
            List of all prompt dicts
        """
        if not self.manifest:
            _ = await self.load_manifest()

        all_prompts: list[dict[str, object]] = []
        for category in self.get_categories():
            prompts = await self.load_category(category)
            all_prompts.extend(prompts)

        return all_prompts
