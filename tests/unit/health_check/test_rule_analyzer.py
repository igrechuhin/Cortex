"""Tests for rule analyzer."""

from pathlib import Path

import pytest

from cortex.health_check.rule_analyzer import RuleAnalyzer


class TestRuleAnalyzer:
    """Test rule analyzer functionality."""

    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        """Create temporary project root."""
        return tmp_path

    @pytest.fixture
    def analyzer(self, project_root: Path) -> RuleAnalyzer:
        """Create rule analyzer instance."""
        return RuleAnalyzer(project_root)

    @pytest.mark.asyncio
    async def test_analyze_no_rules_dir(self, analyzer: RuleAnalyzer):
        """Test analyze when rules directory doesn't exist."""
        result = await analyzer.analyze()
        assert "total" in result
        assert result["total"] == 0
        assert result["categories"] == []
        assert result["merge_opportunities"] == []
        assert result["optimization_opportunities"] == []

    @pytest.mark.asyncio
    async def test_get_categories(self, analyzer: RuleAnalyzer):
        """Test getting rule categories."""
        rules = {"category1": {"rule1.mdc": "content"}, "category2": {}}
        categories = analyzer._get_categories(rules)
        assert "category1" in categories
        assert "category2" in categories

    @pytest.mark.asyncio
    async def test_find_within_category_opportunities(self, analyzer: RuleAnalyzer):
        """Test finding merge opportunities within category."""
        rules = {
            "python": {
                "rule1.mdc": "This is test content.",
                "rule2.mdc": "This is test content.",
            }
        }
        opportunities = analyzer._find_within_category_opportunities(rules)
        assert len(opportunities) > 0

    @pytest.mark.asyncio
    async def test_find_cross_category_opportunities(self, analyzer: RuleAnalyzer):
        """Test finding merge opportunities across categories."""
        rules = {
            "python": {"rule1.mdc": "This is test content."},
            "typescript": {"rule2.mdc": "This is test content."},
        }
        opportunities = analyzer._find_cross_category_opportunities(rules)
        # May or may not find opportunities depending on similarity
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_find_optimization_opportunities(self, analyzer: RuleAnalyzer):
        """Test finding optimization opportunities."""
        rules = {
            "python": {"rule1.mdc": "Small rule content."},
        }
        opportunities = await analyzer._find_optimization_opportunities(rules)
        assert isinstance(opportunities, list)

    @pytest.mark.asyncio
    async def test_scan_rules_with_files(self, analyzer: RuleAnalyzer, tmp_path: Path):
        """Test scanning rules when files exist."""
        rules_dir = tmp_path / ".cortex" / "synapse" / "rules"
        python_dir = rules_dir / "python"
        python_dir.mkdir(parents=True)
        test_file = python_dir / "test.mdc"
        test_file.write_text("# Test Rule\nRule content here")

        # Update analyzer's rules_dir to point to our test directory
        analyzer.rules_dir = rules_dir

        rules = await analyzer._scan_rules()
        assert "python" in rules
        assert "test.mdc" in rules["python"]
        assert "Rule content here" in rules["python"]["test.mdc"]
