"""Tests for constitutional compliance scanning."""

import json
from pathlib import Path

import pytest

from cortex.tools.plans.constitutional_scan import (
    COMPLIANCE_SECTION_HEADER,
    append_compliance_section,
    apply_constitutional_compliance,
    extract_constitution_rule_lines,
    find_potential_violations,
)


class TestExtractConstitutionRuleLines:
    def test_collects_principles_and_hard_limits_bullets(self) -> None:
        md = """## Principles

- No foobar widgets
- Must stay small

## Hard limits

- No baz patterns

## Other

ignored
"""
        rules = extract_constitution_rule_lines(md)
        assert "- No foobar widgets" not in rules
        assert "No foobar widgets" in rules
        assert "No baz patterns" in rules


class TestFindPotentialViolations:
    def test_detects_no_prefix_overlap(self) -> None:
        rules = ["No foobar widgets"]
        plan = "We will ship foobar widgets in v1."
        violations = find_potential_violations(rules, plan)
        assert len(violations) == 1
        assert "[VIOLATION:" in violations[0]

    def test_clean_plan(self) -> None:
        rules = ["No foobar widgets"]
        plan = "# Plan\n\nUse explicit models only."
        assert find_potential_violations(rules, plan) == []


class TestAppendComplianceSection:
    def test_appends_section(self) -> None:
        plan = "# T\n\nBody.\n"
        out = append_compliance_section(plan, ["[VIOLATION: x] y"])
        assert COMPLIANCE_SECTION_HEADER in out
        assert "[VIOLATION: x] y" in out


@pytest.mark.asyncio
class TestInitConstitutionTool:
    async def test_creates_from_template(self, tmp_path: Path) -> None:
        from cortex.core.path_resolver import get_constitution_template_path
        from cortex.tools.files.manage_file_helpers import execute_file_operation
        from cortex.tools.files.operation_helpers import FileOperation
        from tests.helpers.path_helpers import ensure_test_cortex_structure

        _ = ensure_test_cortex_structure(tmp_path)
        tpl_path = get_constitution_template_path(tmp_path)
        _ = tpl_path.parent.mkdir(parents=True, exist_ok=True)
        _ = tpl_path.write_text("# T\n\n## Principles\n\n- No z\n", encoding="utf-8")
        out = await execute_file_operation(
            tmp_path,
            "constitution.md",
            FileOperation.INIT_CONSTITUTION,
            None,
            False,
            None,
            None,
        )
        assert json.loads(out).get("status") == "success"

    async def test_second_call_skips(self, tmp_path: Path) -> None:
        from cortex.core.path_resolver import get_constitution_template_path
        from cortex.tools.files.manage_file_helpers import execute_file_operation
        from cortex.tools.files.operation_helpers import FileOperation
        from tests.helpers.path_helpers import ensure_test_cortex_structure

        _ = ensure_test_cortex_structure(tmp_path)
        tpl_path = get_constitution_template_path(tmp_path)
        _ = tpl_path.parent.mkdir(parents=True, exist_ok=True)
        _ = tpl_path.write_text("# T\n", encoding="utf-8")
        _ = await execute_file_operation(
            tmp_path,
            "constitution.md",
            FileOperation.INIT_CONSTITUTION,
            None,
            False,
            None,
            None,
        )
        out2 = await execute_file_operation(
            tmp_path,
            "constitution.md",
            FileOperation.INIT_CONSTITUTION,
            None,
            False,
            None,
            None,
        )
        assert json.loads(out2).get("skipped") is True


class TestApplyConstitutionalCompliance:
    def test_skips_when_constitution_missing(self, tmp_path: Path) -> None:
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = mb.mkdir(parents=True)
        text, zero = apply_constitutional_compliance(tmp_path, "# P\n\nok\n")
        assert zero == 0
        assert "Constitutional Compliance" not in text

    def test_adds_section_when_rule_hit(self, tmp_path: Path) -> None:
        mb = tmp_path / ".cortex" / "memory-bank"
        _ = mb.mkdir(parents=True)
        cons = mb / "constitution.md"
        _ = cons.write_text(
            "## Principles\n\n- No purple elephants\n\n## Hard limits\n\n",
            encoding="utf-8",
        )
        plan_md = "# Plan\n\nWe will add purple elephants to the API.\n"
        out, count = apply_constitutional_compliance(tmp_path, plan_md)
        assert count == 1
        assert COMPLIANCE_SECTION_HEADER in out
        assert "purple elephants" in out
