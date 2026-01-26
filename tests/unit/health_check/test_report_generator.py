"""Tests for report generator."""

from pathlib import Path

import pytest

from cortex.health_check.models import HealthCheckReport
from cortex.health_check.report_generator import ReportGenerator


class TestReportGenerator:
    """Test report generator functionality."""

    @pytest.fixture
    def generator(self) -> ReportGenerator:
        """Create report generator instance."""
        return ReportGenerator()

    @pytest.fixture
    def sample_report(self) -> HealthCheckReport:
        """Create sample health-check report."""
        return {
            "status": "success",
            "analysis_type": "full",
            "prompts": {
                "total": 5,
                "merge_opportunities": [
                    {
                        "files": ["prompt1.md", "prompt2.md"],
                        "similarity": 0.85,
                        "merge_suggestion": "Consider merging",
                        "quality_impact": "positive",
                        "estimated_savings": "15% reduction",
                    }
                ],
                "optimization_opportunities": [],
            },
            "rules": {
                "total": 10,
                "categories": ["python", "general"],
                "merge_opportunities": [],
                "optimization_opportunities": [],
            },
            "tools": {
                "total": 20,
                "merge_opportunities": [],
                "consolidation_opportunities": [],
                "optimization_opportunities": [],
            },
            "recommendations": ["Recommendation 1", "Recommendation 2"],
        }

    def test_generate_markdown_report(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating markdown report."""
        content = generator.generate_markdown_report(sample_report)
        assert "# Health-Check Analysis Report" in content
        assert "Prompts Analysis" in content
        assert "Rules Analysis" in content
        assert "Tools Analysis" in content
        assert "Recommendations" in content

    def test_generate_markdown_report_with_output_path(
        self,
        generator: ReportGenerator,
        sample_report: HealthCheckReport,
        tmp_path: Path,
    ):
        """Test generating markdown report with output path."""
        output_path = tmp_path / "report.md"
        content = generator.generate_markdown_report(sample_report, output_path)
        assert output_path.exists()
        assert "# Health-Check Analysis Report" in content

    def test_generate_json_report(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating JSON report."""
        content = generator.generate_json_report(sample_report)
        assert '"status": "success"' in content
        assert '"analysis_type": "full"' in content

    def test_generate_json_report_with_output_path(
        self,
        generator: ReportGenerator,
        sample_report: HealthCheckReport,
        tmp_path: Path,
    ):
        """Test generating JSON report with output path."""
        output_path = tmp_path / "report.json"
        content = generator.generate_json_report(sample_report, output_path)
        assert output_path.exists()
        assert '"status": "success"' in content

    def test_generate_header(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating report header."""
        lines = generator._generate_header(sample_report)
        assert len(lines) > 0
        assert "# Health-Check Analysis Report" in lines[0]

    def test_generate_prompts_section(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating prompts section."""
        lines = generator._generate_prompts_section(sample_report)
        assert "## Prompts Analysis" in lines[0]
        assert "Total" in "".join(lines)

    def test_generate_rules_section(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating rules section."""
        lines = generator._generate_rules_section(sample_report)
        assert "## Rules Analysis" in lines[0]

    def test_generate_tools_section(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating tools section."""
        lines = generator._generate_tools_section(sample_report)
        assert "## Tools Analysis" in lines[0]

    def test_generate_recommendations_section(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating recommendations section."""
        lines = generator._generate_recommendations_section(sample_report)
        assert "## Recommendations" in lines[0]
        assert "Recommendation 1" in "".join(lines)

    def test_generate_recommendations_section_empty(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating recommendations section with no recommendations."""
        sample_report["recommendations"] = []
        lines = generator._generate_recommendations_section(sample_report)
        assert len(lines) == 0

    def test_generate_prompts_section_with_merge_opportunities(
        self, generator: ReportGenerator, sample_report: HealthCheckReport
    ):
        """Test generating prompts section with merge opportunities."""
        lines = generator._generate_prompts_section(sample_report)
        assert "### Merge Opportunities" in "".join(lines)
        assert "prompt1.md" in "".join(lines)
