"""Tests for dependency mapper."""

from pathlib import Path

import pytest

from cortex.health_check.dependency_mapper import DependencyMapper


class TestDependencyMapper:
    """Test dependency mapper functionality."""

    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        """Create temporary project root."""
        return tmp_path

    @pytest.fixture
    def mapper(self, project_root: Path) -> DependencyMapper:
        """Create dependency mapper instance."""
        return DependencyMapper(project_root)

    @pytest.mark.asyncio
    async def test_map_prompt_dependencies_empty(self, mapper: DependencyMapper):
        """Test mapping prompt dependencies with empty inputs."""
        result = await mapper.map_prompt_dependencies({})
        assert result == {}

    @pytest.mark.asyncio
    async def test_map_prompt_dependencies(self, mapper: DependencyMapper):
        """Test mapping dependencies for prompts."""
        prompts = {"prompt1.md": "Content", "prompt2.md": "See prompt1.md"}
        result = await mapper.map_prompt_dependencies(prompts)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_map_rule_dependencies(self, mapper: DependencyMapper):
        """Test mapping dependencies for rules."""
        rules = {"python": {"rule1.mdc": "Content"}}
        result = await mapper.map_rule_dependencies(rules)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_map_tool_dependencies(self, mapper: DependencyMapper):
        """Test mapping dependencies for tools."""
        from typing import cast

        tools = {"tool1": {"docstring": "Content", "body": "Code"}}
        result = await mapper.map_tool_dependencies(
            cast(dict[str, dict[str, object]], tools)
        )
        assert isinstance(result, dict)

    def test_extract_prompt_references(self, mapper: DependencyMapper):
        """Test extracting prompt references."""
        content = "See prompt1.md for details. Also check prompt2.md."
        prompt_names = {"prompt1.md", "prompt2.md", "prompt3.md"}
        refs = mapper._extract_prompt_references(content, prompt_names)  # type: ignore[attr-defined]
        assert "prompt1.md" in refs
        assert "prompt2.md" in refs
        assert "prompt3.md" not in refs

    def test_extract_rule_references(self, mapper: DependencyMapper):
        """Test extracting rule references."""
        content = "See python/coding.mdc for details."
        rule_names = {"python/coding.mdc", "general/rules.mdc"}
        refs = mapper._extract_rule_references(content, rule_names)  # type: ignore[attr-defined]
        assert "python/coding.mdc" in refs

    def test_extract_tool_references(self, mapper: DependencyMapper):
        """Test extracting tool references."""
        content = "This tool uses tool1 and tool2 for processing."
        tool_names = {"tool1", "tool2", "tool3"}
        refs = mapper._extract_tool_references(content, tool_names)  # type: ignore[attr-defined]
        assert "tool1" in refs
        assert "tool2" in refs
        assert "tool3" not in refs
