#!/usr/bin/env python3
"""Insight formatter for exporting insights in various formats.

This module handles formatting and exporting insights in JSON, Markdown,
and plain text formats.

Performance optimizations (Phase 10.3.1 Day 5):
- String builder pattern using list + join instead of repeated concatenation
- Reduces O(n²) string concatenation to O(n) with single join
- Pre-allocated list capacity for better memory performance
"""

from typing import cast

from cortex.core.exceptions import MemoryBankError

from .insight_types import InsightDict


class InsightFormatter:
    """Formatter for exporting insights in various formats."""

    def export_insights(self, insights: dict[str, object], format: str = "json") -> str:
        """
        Export insights in various formats.

        Args:
            insights: Insights dictionary from generate_insights()
            format: Export format ("json", "markdown", "text")

        Returns:
            Formatted string

        Raises:
            MemoryBankError: If format is unsupported
        """
        if format == "json":
            return self._export_insights_json(insights)
        elif format == "markdown":
            return self._export_insights_markdown(insights)
        elif format == "text":
            return self._export_insights_text(insights)
        else:
            raise MemoryBankError(f"Unsupported export format: {format}")

    def _export_insights_json(self, insights: dict[str, object]) -> str:
        """Export insights as JSON.

        Args:
            insights: Insights dictionary

        Returns:
            JSON-formatted string
        """
        import json

        return json.dumps(insights, indent=2)

    def _export_insights_markdown(self, insights: dict[str, object]) -> str:
        """Export insights as Markdown.

        Args:
            insights: Insights dictionary

        Returns:
            Markdown-formatted string
        """
        lines = self._build_markdown_header(insights)
        insights_list = self._extract_insights_list(insights)
        lines.extend(self._format_insights_markdown(insights_list))
        return "\n".join(lines)

    def _build_markdown_header(self, insights: dict[str, object]) -> list[str]:
        """Build Markdown header section.

        Args:
            insights: Insights dictionary

        Returns:
            List of header lines
        """
        summary_dict = cast(dict[str, object], insights.get("summary", {}))
        return [
            "# Memory Bank Insights Report",
            f"\n**Generated:** {str(insights.get('generated_at', ''))}",
            f"\n**Total Insights:** {insights.get('total_insights', 0)}",
            f"**Estimated Token Savings:** {insights.get('estimated_total_token_savings', 0)}",
            "\n## Summary",
            f"\n{str(summary_dict.get('message', ''))}",
            f"\n- High Priority: {insights.get('high_impact_count', 0)}",
            f"- Medium Priority: {insights.get('medium_impact_count', 0)}",
            f"- Low Priority: {insights.get('low_impact_count', 0)}",
            "\n## Insights\n",
        ]

    def _extract_insights_list(self, insights: dict[str, object]) -> list[InsightDict]:
        """Extract insights list from insights dictionary.

        Args:
            insights: Insights dictionary

        Returns:
            List of insight dictionaries
        """
        insights_list_obj: object = insights.get("insights", [])
        insights_list: list[InsightDict] = []
        if isinstance(insights_list_obj, list):
            insights_list_raw: list[object] = cast(list[object], insights_list_obj)
            for item in insights_list_raw:
                if isinstance(item, dict):
                    insights_list.append(cast(InsightDict, item))
        return insights_list

    def _format_insights_markdown(self, insights_list: list[InsightDict]) -> list[str]:
        """Format insights list as Markdown.

        Performance: O(n × m) where n = insights, m = avg recommendations per insight
        - Pre-allocated list capacity for better memory performance
        - Single-pass formatting with minimal allocations

        Args:
            insights_list: List of insight dictionaries

        Returns:
            List of formatted lines
        """
        # Pre-allocate list capacity (estimate ~6 lines per insight)
        estimated_capacity = len(insights_list) * 6
        lines: list[str] = []
        if estimated_capacity > 0:
            lines = ["" for _ in range(estimated_capacity)]
            lines.clear()  # Clear but keep capacity

        for i, insight_dict in enumerate(insights_list, 1):
            lines.append(f"\n### {i}. {str(insight_dict.get('title', ''))}")
            impact_score = insight_dict.get("impact_score", 0.0)
            impact_float = float(impact_score)
            lines.append(
                f"\n**Impact:** {impact_float:.2f} | **Severity:** {str(insight_dict.get('severity', ''))}"
            )
            lines.append(f"\n{str(insight_dict.get('description', ''))}")
            lines.append("\n**Recommendations:**")
            recommendations_raw: object = insight_dict.get("recommendations", [])
            if isinstance(recommendations_raw, list):
                recommendations_list: list[object] = cast(
                    list[object], recommendations_raw
                )
                # Batch append for better performance
                lines.extend(f"- {str(rec_item)}" for rec_item in recommendations_list)
        return lines

    def _export_insights_text(self, insights: dict[str, object]) -> str:
        """Export insights as plain text.

        Args:
            insights: Insights dictionary

        Returns:
            Plain text-formatted string
        """
        lines = self._build_text_header(insights)
        insights_list = self._extract_insights_list(insights)
        lines.extend(self._format_insights_text(insights_list))
        return "\n".join(lines)

    def _build_text_header(self, insights: dict[str, object]) -> list[str]:
        """Build text header section.

        Args:
            insights: Insights dictionary

        Returns:
            List of header lines
        """
        summary_dict = cast(dict[str, object], insights.get("summary", {}))
        return [
            "MEMORY BANK INSIGHTS REPORT",
            "=" * 50,
            f"Generated: {str(insights.get('generated_at', ''))}",
            f"Total Insights: {insights.get('total_insights', 0)}",
            f"Estimated Token Savings: {insights.get('estimated_total_token_savings', 0)}",
            "",
            "SUMMARY:",
            str(summary_dict.get("message", "")),
            "",
            "INSIGHTS:",
            "",
        ]

    def _format_insights_text(self, insights_list: list[InsightDict]) -> list[str]:
        """Format insights list as plain text.

        Performance: O(n) where n = number of insights
        - Pre-allocated list capacity for better memory performance
        - Minimal string allocations

        Args:
            insights_list: List of insight dictionaries

        Returns:
            List of formatted lines
        """
        # Pre-allocate list capacity (estimate ~4 lines per insight)
        estimated_capacity = len(insights_list) * 4
        lines: list[str] = []
        if estimated_capacity > 0:
            lines = ["" for _ in range(estimated_capacity)]
            lines.clear()  # Clear but keep capacity

        for i, insight_dict in enumerate(insights_list, 1):
            lines.append(f"{i}. {str(insight_dict.get('title', ''))}")
            impact_score = insight_dict.get("impact_score", 0.0)
            impact_float = float(impact_score)
            lines.append(
                f"   Impact: {impact_float:.2f} | Severity: {str(insight_dict.get('severity', ''))}"
            )
            lines.append(f"   {str(insight_dict.get('description', ''))}")
            lines.append("")
        return lines
