"""Dependency mapping for health-check analysis."""

import re
from pathlib import Path


class DependencyMapper:
    """Maps dependencies between prompts, rules, and tools."""

    def __init__(self, project_root: Path):
        """Initialize dependency mapper.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)

    async def map_prompt_dependencies(
        self, prompts: dict[str, str]
    ) -> dict[str, list[str]]:
        """Map dependencies between prompts.

        Args:
            prompts: Dictionary of prompt names to content

        Returns:
            Dictionary mapping prompt names to list of referenced prompts
        """
        dependencies: dict[str, list[str]] = {}

        for name, content in prompts.items():
            refs = self._extract_prompt_references(content, set(prompts.keys()))
            dependencies[name] = refs

        return dependencies

    def _extract_prompt_references(
        self, content: str, prompt_names: set[str]
    ) -> list[str]:
        """Extract references to other prompts from content.

        Args:
            content: Prompt content
            prompt_names: Set of available prompt names

        Returns:
            List of referenced prompt names
        """
        references: list[str] = []

        # Look for references like "see prompt.md" or "prompt.md"
        pattern = r"([a-zA-Z0-9_-]+\.md)"
        matches = re.findall(pattern, content)

        for match in matches:
            if match in prompt_names:
                references.append(match)

        return list(set(references))  # Remove duplicates

    async def map_rule_dependencies(
        self, rules: dict[str, dict[str, str]]
    ) -> dict[str, list[str]]:
        """Map dependencies between rules.

        Args:
            rules: Dictionary of rules by category

        Returns:
            Dictionary mapping rule paths to list of referenced rules
        """
        dependencies: dict[str, list[str]] = {}

        all_rule_names: set[str] = set()
        for category, category_rules in rules.items():
            for name in category_rules.keys():
                all_rule_names.add(f"{category}/{name}")

        for category, category_rules in rules.items():
            for name, content in category_rules.items():
                rule_path = f"{category}/{name}"
                refs = self._extract_rule_references(content, all_rule_names)
                dependencies[rule_path] = refs

        return dependencies

    def _extract_rule_references(self, content: str, rule_names: set[str]) -> list[str]:
        """Extract references to other rules from content.

        Args:
            content: Rule content
            rule_names: Set of available rule paths

        Returns:
            List of referenced rule paths
        """
        references: list[str] = []

        # Look for references like "see rules/category/file.mdc"
        pattern = r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+\.mdc)"
        matches = re.findall(pattern, content)

        for match in matches:
            if match in rule_names:
                references.append(match)

        return list(set(references))  # Remove duplicates

    async def map_tool_dependencies(
        self, tools: dict[str, dict[str, object]]
    ) -> dict[str, list[str]]:
        """Map dependencies between tools.

        Args:
            tools: Dictionary of tool names to tool metadata

        Returns:
            Dictionary mapping tool names to list of referenced tools
        """
        dependencies: dict[str, list[str]] = {}

        for name, tool in tools.items():
            docstring = str(tool.get("docstring", ""))
            body = str(tool.get("body", ""))

            # Extract tool references from docstring and body
            content = docstring + body
            refs = self._extract_tool_references(content, set(tools.keys()))
            dependencies[name] = refs

        return dependencies

    def _extract_tool_references(self, content: str, tool_names: set[str]) -> list[str]:
        """Extract references to other tools from content.

        Args:
            content: Tool content (docstring + body)
            tool_names: Set of available tool names

        Returns:
            List of referenced tool names
        """
        references: list[str] = []

        # Look for tool references in docstrings and code
        for tool_name in tool_names:
            # Check for mentions of tool name
            pattern = rf"\b{tool_name}\b"
            if re.search(pattern, content, re.IGNORECASE):
                references.append(tool_name)

        return list(set(references))  # Remove duplicates
