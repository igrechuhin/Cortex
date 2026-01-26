"""Report generator for health-check analysis."""

import json
from pathlib import Path

from cortex.health_check.models import HealthCheckReport


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
        lines: list[str] = []

        lines.extend(self._generate_header(report))
        lines.extend(self._generate_prompts_section(report))
        lines.extend(self._generate_rules_section(report))
        lines.extend(self._generate_tools_section(report))
        lines.extend(self._generate_recommendations_section(report))

        content = "\n".join(lines)

        if output_path:
            _ = output_path.write_text(content, encoding="utf-8")

        return content

    def _generate_header(self, report: HealthCheckReport) -> list[str]:
        """Generate report header.

        Args:
            report: Health-check report

        Returns:
            Header lines
        """
        return [
            "# Health-Check Analysis Report\n",
            f"**Status**: {report['status']}\n",
            f"**Analysis Type**: {report['analysis_type']}\n\n",
        ]

    def _generate_prompts_section(self, report: HealthCheckReport) -> list[str]:
        """Generate prompts analysis section.

        Args:
            report: Health-check report

        Returns:
            Prompts section lines
        """
        lines: list[str] = []
        lines.append("## Prompts Analysis\n")
        lines.append(f"- **Total**: {report['prompts']['total']}\n")
        lines.append(
            f"- **Merge Opportunities**: {len(report['prompts']['merge_opportunities'])}\n"
        )
        lines.append(
            f"- **Optimization Opportunities**: {len(report['prompts']['optimization_opportunities'])}\n\n"
        )

        if report["prompts"]["merge_opportunities"]:
            lines.append("### Merge Opportunities\n")
            for opp in report["prompts"]["merge_opportunities"]:
                lines.append(f"- **{', '.join(opp['files'])}**")
                lines.append(f"  - Similarity: {opp['similarity']:.2%}")
                lines.append(f"  - Suggestion: {opp['merge_suggestion']}")
                lines.append(f"  - Impact: {opp['quality_impact']}\n")

        return lines

    def _generate_rules_section(self, report: HealthCheckReport) -> list[str]:
        """Generate rules analysis section.

        Args:
            report: Health-check report

        Returns:
            Rules section lines
        """
        lines: list[str] = []
        lines.append("## Rules Analysis\n")
        lines.append(f"- **Total**: {report['rules']['total']}\n")
        lines.append(f"- **Categories**: {', '.join(report['rules']['categories'])}\n")
        lines.append(
            f"- **Merge Opportunities**: {len(report['rules']['merge_opportunities'])}\n"
        )
        lines.append(
            f"- **Optimization Opportunities**: {len(report['rules']['optimization_opportunities'])}\n\n"
        )
        return lines

    def _generate_tools_section(self, report: HealthCheckReport) -> list[str]:
        """Generate tools analysis section.

        Args:
            report: Health-check report

        Returns:
            Tools section lines
        """
        lines: list[str] = []
        lines.append("## Tools Analysis\n")
        lines.append(f"- **Total**: {report['tools']['total']}\n")
        lines.append(
            f"- **Merge Opportunities**: {len(report['tools']['merge_opportunities'])}\n"
        )
        lines.append(
            f"- **Consolidation Opportunities**: {len(report['tools']['consolidation_opportunities'])}\n"
        )
        lines.append(
            f"- **Optimization Opportunities**: {len(report['tools']['optimization_opportunities'])}\n\n"
        )
        return lines

    def _generate_recommendations_section(self, report: HealthCheckReport) -> list[str]:
        """Generate recommendations section.

        Args:
            report: Health-check report

        Returns:
            Recommendations section lines
        """
        lines: list[str] = []
        if report["recommendations"]:
            lines.append("## Recommendations\n")
            for rec in report["recommendations"]:
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
        content = json.dumps(report, indent=2)

        if output_path:
            _ = output_path.write_text(content, encoding="utf-8")

        return content
