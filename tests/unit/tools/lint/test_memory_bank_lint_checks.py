"""Unit tests for memory-bank lint check taxonomy slice."""

from pathlib import Path
from typing import cast

from cortex.tools.lint.memory_bank_lint_checks import (
    CodeClaimCheck,
    CrossRefCheck,
    IndexStalenessCheck,
    LintCheck,
    LintFinding,
    MissingPlanFilesCheck,
    OrphanedPlansCheck,
    StaleActiveContextCheck,
    StaleNumericClaimCheck,
)
from cortex.tools.lint.memory_bank_wiki_checks import OrphanedWikiPagesCheck
from cortex.wiki.wiki_root_files import WikiRootDocument


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content, encoding="utf-8")


def _write_code_claim_fixture(tmp_path: Path, *, config_content: str) -> None:
    _write(tmp_path / ".cortex" / "config" / "lint-config.json", config_content)
    _write(
        tmp_path / ".cortex" / "memory-bank" / "techContext.md",
        "- Runtime (python): 3.11\n",
    )
    _write(tmp_path / "pyproject.toml", "- Runtime (python): 3.13\n")


def _write_quality_snapshot(
    tmp_path: Path, *, tests_run: int, coverage: float = 0.91
) -> None:
    payload = "\n".join(
        [
            "{",
            '  "results": {',
            '    "tests": {',
            f'      "tests_run": {tests_run},',
            f'      "coverage": {coverage}',
            "    }",
            "  }",
            "}",
            "",
        ]
    )
    _write(
        tmp_path / ".cortex" / ".session" / "pre_commit_result_latest.json",
        payload,
    )


def test_lint_finding_is_valid_pydantic_model() -> None:
    finding = LintFinding(
        severity="warning",
        check="orphaned_plans",
        message="Plan is not referenced",
        file=".cortex/plans/example.md",
        line=5,
    )
    assert finding.model_dump()["severity"] == "warning"


def test_orphaned_plans_check_finds_unreferenced_non_archived_plan(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "roadmap.md",
        "- Keep this plan linked. Plan: .cortex/plans/linked.md\n",
    )
    _write(tmp_path / ".cortex" / "plans" / "linked.md", "# linked")
    _write(tmp_path / ".cortex" / "plans" / "orphan.md", "# orphan")
    _write(tmp_path / ".cortex" / "plans" / "archive" / "old.md", "# archived")

    check: LintCheck = cast(LintCheck, OrphanedPlansCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    assert findings[0].check == "orphaned_plans"
    assert findings[0].severity == "warning"
    assert findings[0].file == ".cortex/plans/orphan.md"


def test_missing_plan_files_check_reports_missing_reference_with_line(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "roadmap.md",
        "\n".join(
            [
                "- Existing. Plan: .cortex/plans/existing.md",
                "- Missing. Plan: .cortex/plans/missing.md.",
            ]
        )
        + "\n",
    )
    _write(tmp_path / ".cortex" / "plans" / "existing.md", "# existing")

    check: LintCheck = cast(LintCheck, MissingPlanFilesCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    assert findings[0].check == "missing_plan_files"
    assert findings[0].severity == "error"
    assert findings[0].file == ".cortex/memory-bank/roadmap.md"
    assert findings[0].line == 2
    assert "missing.md" in findings[0].message


def test_missing_plan_files_check_parses_markdown_link_plan_path(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "roadmap.md",
        "- Plan: [Memory Bank Lint](../plans/memory-bank-lint.md) - PENDING.\n",
    )
    _write(tmp_path / ".cortex" / "plans" / "memory-bank-lint.md", "# existing\n")

    check: LintCheck = cast(LintCheck, MissingPlanFilesCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_stale_active_context_check_reports_old_date_missing_from_progress(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        "## Completed Work (2000-01-01)\n- old entry\n",
    )
    _write(
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
        "## 2026-04-07\n- unrelated\n",
    )

    check: LintCheck = cast(LintCheck, StaleActiveContextCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    assert findings[0].check == "stale_active_context"
    assert findings[0].severity == "warning"
    assert findings[0].file == ".cortex/memory-bank/activeContext.md"
    assert findings[0].line == 1
    assert "2000-01-01" in findings[0].message


def test_stale_active_context_check_skips_old_date_when_progress_matches(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        "## Completed Work (2000-01-01)\n- old entry\n",
    )
    _write(
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
        "## 2000-01-01\n- resolved\n",
    )

    check: LintCheck = cast(LintCheck, StaleActiveContextCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_cross_ref_check_reports_missing_wiki_page_references(tmp_path: Path) -> None:
    _write(
        tmp_path / ".cortex" / "wiki" / WikiRootDocument.INDEX.value,
        "\n".join(
            [
                "- Existing wiki link: [[pages/known]]",
                "- Missing wiki link: [[pages/missing]]",
                "- Missing markdown link: [Spec](specs/unknown.md)",
            ]
        )
        + "\n",
    )
    _write(tmp_path / ".cortex" / "wiki" / "pages" / "known.md", "# known")

    check: LintCheck = cast(LintCheck, CrossRefCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 2
    assert all(finding.check == "cross_ref" for finding in findings)
    assert findings[0].severity == "warning"
    assert findings[0].file == f".cortex/wiki/{WikiRootDocument.INDEX.value}"
    assert "pages/missing.md" in findings[0].message
    assert findings[1].line == 3


def test_cross_ref_check_returns_empty_when_wiki_missing(tmp_path: Path) -> None:
    check: LintCheck = cast(LintCheck, CrossRefCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_orphaned_wiki_pages_check_reports_unlinked_page(tmp_path: Path) -> None:
    _write(tmp_path / ".cortex" / "wiki" / WikiRootDocument.INDEX.value, "# Index\n")
    _write(tmp_path / ".cortex" / "wiki" / "guides" / "linked.md", "# linked\n")
    _write(tmp_path / ".cortex" / "wiki" / "guides" / "orphan.md", "# orphan\n")
    _write(
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        "- reference: [[guides/linked]]\n",
    )

    check: LintCheck = cast(LintCheck, OrphanedWikiPagesCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 2
    assert all(finding.check == "orphaned_wiki_pages" for finding in findings)
    assert all(finding.severity == "warning" for finding in findings)
    orphan_files = {finding.file for finding in findings}
    assert ".cortex/wiki/guides/orphan.md" in orphan_files


def test_orphaned_wiki_pages_check_skips_page_linked_from_wiki(tmp_path: Path) -> None:
    _write(
        tmp_path / ".cortex" / "wiki" / WikiRootDocument.INDEX.value,
        "- link: [[guides/child]]\n",
    )
    _write(tmp_path / ".cortex" / "wiki" / "guides" / "child.md", "# child\n")

    check: LintCheck = cast(LintCheck, OrphanedWikiPagesCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_index_staleness_check_reports_page_missing_from_catalog_table(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "wiki" / WikiRootDocument.INDEX.value,
        "\n".join(
            [
                "| Page | Category | Summary | Sources |",
                "|------|----------|---------|---------|",
                "| [Listed](concepts/listed.md) | concepts | one | src |",
                "",
            ]
        ),
    )
    _write(tmp_path / ".cortex" / "wiki" / "concepts" / "listed.md", "# ok\n")
    _write(tmp_path / ".cortex" / "wiki" / "concepts" / "missing.md", "# orphan\n")

    check: LintCheck = cast(LintCheck, IndexStalenessCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    assert findings[0].check == "index_staleness"
    assert findings[0].severity == "warning"
    assert findings[0].file == ".cortex/wiki/concepts/missing.md"
    assert f"missing from {WikiRootDocument.INDEX.value} catalog" in findings[0].message


def test_index_staleness_check_skips_sources_and_schema(tmp_path: Path) -> None:
    _write(
        tmp_path / ".cortex" / "wiki" / WikiRootDocument.INDEX.value,
        "| Page | Category | Summary | Sources |\n|------|----------|---------|---------|\n",
    )
    _write(
        tmp_path / ".cortex" / "wiki" / WikiRootDocument.SCHEMA.value,
        "# schema\n",
    )
    _write(tmp_path / ".cortex" / "wiki" / "sources" / "raw.md", "# raw\n")

    check: LintCheck = cast(LintCheck, IndexStalenessCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_index_staleness_check_returns_empty_when_wiki_missing(tmp_path: Path) -> None:
    check: LintCheck = cast(LintCheck, IndexStalenessCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_orphaned_wiki_pages_check_skips_page_linked_from_memory_bank(
    tmp_path: Path,
) -> None:
    _write(tmp_path / ".cortex" / "wiki" / "guides" / "child.md", "# child\n")
    _write(
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        "- wiki ref: [[guides/child]]\n",
    )

    check: LintCheck = cast(LintCheck, OrphanedWikiPagesCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_orphaned_wiki_pages_check_returns_empty_when_wiki_missing(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        "- only memory-bank file\n",
    )

    check: LintCheck = cast(LintCheck, OrphanedWikiPagesCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_orphaned_wiki_pages_check_reports_source_without_summary_reference(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "sources" / "rfc-update.md", "# source\n"
    )
    _write(
        tmp_path
        / ".cortex"
        / "memory-bank"
        / "queries"
        / "query-not-related-2026-04-08.md",
        "# unrelated query artifact\n",
    )

    check: LintCheck = cast(LintCheck, OrphanedWikiPagesCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check == "orphaned_wiki_pages"
    assert finding.severity == "warning"
    assert finding.file == ".cortex/memory-bank/sources/rfc-update.md"
    assert "no corresponding summary page reference" in finding.message


def test_orphaned_wiki_pages_check_reports_summary_referencing_missing_source(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path
        / ".cortex"
        / "memory-bank"
        / "queries"
        / "query-rfc-update-2026-04-08.md",
        "- Source: [.cortex/memory-bank/sources/missing-source.md](.cortex/memory-bank/sources/missing-source.md)\n",
    )

    check: LintCheck = cast(LintCheck, OrphanedWikiPagesCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check == "orphaned_wiki_pages"
    assert finding.severity == "warning"
    assert finding.file == ".cortex/memory-bank/queries/query-rfc-update-2026-04-08.md"
    assert "references missing ingest source" in finding.message
    assert "sources/missing-source.md" in finding.message


def test_stale_active_context_check_skips_recent_date(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "activeContext.md",
        "## Completed Work (2999-01-01)\n- future-like recent sentinel\n",
    )
    _write(
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
        "## 2026-04-07\n- unrelated\n",
    )

    check: LintCheck = cast(LintCheck, StaleActiveContextCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_code_claim_check_reports_mismatch_from_lint_config(tmp_path: Path) -> None:
    config = "\n".join(
        [
            "{",
            '  "code_claim_checks": [',
            "    {",
            '      "file": ".cortex/memory-bank/techContext.md",',
            '      "pattern": "python",',
            '      "verify_against": "pyproject.toml"',
            "    }",
            "  ]",
            "}",
        ]
    )
    _write_code_claim_fixture(tmp_path, config_content=f"{config}\n")

    check: LintCheck = cast(LintCheck, CodeClaimCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check == "code_claim"
    assert finding.severity == "warning"
    assert finding.file == ".cortex/memory-bank/techContext.md"
    assert finding.line == 1
    assert "expected '3.11'" in finding.message
    assert "actual '3.13'" in finding.message


def test_code_claim_check_returns_empty_when_lint_config_missing(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".cortex" / "memory-bank" / "techContext.md",
        "- Runtime (python): 3.11\n",
    )
    _write(tmp_path / "pyproject.toml", "- Runtime (python): 3.13\n")

    check: LintCheck = cast(LintCheck, CodeClaimCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_code_claim_check_returns_empty_when_lint_config_is_malformed(
    tmp_path: Path,
) -> None:
    _write_code_claim_fixture(tmp_path, config_content="{ invalid json\n")

    check: LintCheck = cast(LintCheck, CodeClaimCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_stale_numeric_claim_check_warns_for_stale_test_count(tmp_path: Path) -> None:
    _write_quality_snapshot(tmp_path, tests_run=6500)
    _write(
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
        "\n".join(
            [
                "# Progress Log",
                "",
                "## What Works",
                "",
                "Pre-commit pipeline; 3702 tests, 90.36% coverage.",
                "",
            ]
        ),
    )

    check: LintCheck = cast(LintCheck, StaleNumericClaimCheck())
    findings = check.run(tmp_path)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check == "stale_numeric_claim"
    assert finding.severity == "warning"
    assert finding.file == ".cortex/memory-bank/progress.md"
    assert "3702 tests vs latest quality result 6500 tests" in finding.message


def test_stale_numeric_claim_check_returns_empty_for_fresh_count(
    tmp_path: Path,
) -> None:
    _write_quality_snapshot(tmp_path, tests_run=6500)
    _write(
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
        "\n".join(
            [
                "# Progress Log",
                "",
                "## What Works",
                "",
                "Pre-commit pipeline; 6500 tests, 91.00% coverage.",
                "",
            ]
        ),
    )

    check: LintCheck = cast(LintCheck, StaleNumericClaimCheck())
    findings = check.run(tmp_path)

    assert findings == []


def test_stale_numeric_claim_check_noops_without_what_works_section(
    tmp_path: Path,
) -> None:
    _write_quality_snapshot(tmp_path, tests_run=6500)
    _write(
        tmp_path / ".cortex" / "memory-bank" / "progress.md",
        "# Progress Log\n\n## 2026-04-14\n- entry\n",
    )

    check: LintCheck = cast(LintCheck, StaleNumericClaimCheck())
    findings = check.run(tmp_path)

    assert findings == []
