"""Report generator for health-check analysis."""

from pathlib import Path

from cortex.health_check.models import HealthCheckReport, HealthCheckReportPayload


class ReportGenerator:
    """Generates health-check reports."""

    def generate_markdown_report(
        self, report: HealthCheckReport, output_path: Path | None = None
    ) -> str:
        """Generate markdown report.

        Args:
            report: Health-check report
            output_path: Optional path to save report

        Returns:
            Markdown report content
        """
        payload = report
        lines: list[str] = []

        lines.extend(self._generate_header(payload))
        lines.extend(self._generate_prompts_section(payload))
        lines.extend(self._generate_rules_section(payload))
        lines.extend(self._generate_tools_section(payload))
        lines.extend(self._generate_recommendations_section(payload))

        content = "\n".join(lines)

        if output_path:
            _ = output_path.write_text(content, encoding="utf-8")

        return content

    def _generate_header(self, report: HealthCheckReportPayload) -> list[str]:
        """Generate report header.

        Args:
            report: Health-check report

        Returns:
            Header lines
        """
        return [
            "# Health-Check Analysis Report\n",
            f"**Status**: {report.status}\n",
            f"**Analysis Type**: {report.analysis_type}\n\n",
        ]

    def _generate_prompts_section(self, report: HealthCheckReportPayload) -> list[str]:
        """Generate prompts analysis section.

        Args:
            report: Health-check report

        Returns:
            Prompts section lines
        """
        prompts = report.prompts
        lines: list[str] = []
        lines.append("## Prompts Analysis\n")
        lines.append(f"- **Total**: {prompts.total}\n")
        lines.append(
            "- **Merge Opportunities**: " + f"{len(prompts.merge_opportunities)}\n"
        )
        lines.append(
            "- **Optimization Opportunities**: "
            + f"{len(prompts.optimization_opportunities)}\n\n"
        )

        if prompts.merge_opportunities:
            lines.append("### Merge Opportunities\n")
            for opp in prompts.merge_opportunities:
                lines.append(f"- **{', '.join(opp.files)}**")
                lines.append(f"  - Similarity: {opp.similarity:.2%}")
                lines.append(f"  - Suggestion: {opp.merge_suggestion}")
                lines.append(f"  - Impact: {opp.quality_impact}\n")

        return lines

    def _generate_rules_section(self, report: HealthCheckReportPayload) -> list[str]:
        """Generate rules analysis section.

        Args:
            report: Health-check report

        Returns:
            Rules section lines
        """
        rules = report.rules
        lines: list[str] = []
        lines.append("## Rules Analysis\n")
        lines.append(f"- **Total**: {rules.total}\n")
        lines.append(f"- **Categories**: {', '.join(rules.categories)}\n")
        lines.append(
            "- **Merge Opportunities**: " + f"{len(rules.merge_opportunities)}\n"
        )
        lines.append(
            "- **Optimization Opportunities**: "
            + f"{len(rules.optimization_opportunities)}\n\n"
        )
        return lines

    def _generate_tools_section(self, report: HealthCheckReportPayload) -> list[str]:
        """Generate tools analysis section.

        Args:
            report: Health-check report

        Returns:
            Tools section lines
        """
        tools = report.tools
        lines: list[str] = []
        lines.append("## Tools Analysis\n")
        lines.append(f"- **Total**: {tools.total}\n")
        lines.append(
            "- **Merge Opportunities**: " + f"{len(tools.merge_opportunities)}\n"
        )
        lines.append(
            "- **Consolidation Opportunities**: "
            + f"{len(tools.consolidation_opportunities)}\n"
        )
        lines.append(
            "- **Optimization Opportunities**: "
            + f"{len(tools.optimization_opportunities)}\n\n"
        )
        return lines

    def _generate_recommendations_section(
        self, report: HealthCheckReportPayload
    ) -> list[str]:
        """Generate recommendations section.

        Args:
            report: Health-check report

        Returns:
            Recommendations section lines
        """
        lines: list[str] = []
        if report.recommendations:
            lines.append("## Recommendations\n")
            for rec in report.recommendations:
                lines.append(f"- {rec}\n")
        return lines

    def generate_json_report(
        self, report: HealthCheckReport, output_path: Path | None = None
    ) -> str:
        """Generate JSON report.

        Args:
            report: Health-check report
            output_path: Optional path to save report

        Returns:
            JSON report content
        """
        content = report.model_dump_json(indent=2)

        if output_path:
            _ = output_path.write_text(content, encoding="utf-8")

        return content
