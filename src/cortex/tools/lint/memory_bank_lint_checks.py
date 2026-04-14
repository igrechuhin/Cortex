"""Taxonomy and core checks for memory-bank linting."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.wiki.categories import WikiCategoryDir
from cortex.wiki.ingest_wiki import index_catalog_linked_page_paths
from cortex.wiki.wiki_root_files import WIKI_ROOT_DOCUMENT_NAMES, WikiRootDocument

_PLAN_PATH_PATTERN = "Plan:"
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]|\[[^\]]+\]\(([^)]+)\)")
_CLAIM_PATTERN_GROUP = re.compile(r"\((?P<key>[^)]+)\):\s*(?P<value>.+)")
_MARKDOWN_LINK_PATH_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_WHAT_WORKS_HEADING = "## What Works"
_H2_HEADING_PATTERN = re.compile(r"^##\s+")
_TEST_COVERAGE_CLAIM_PATTERN = re.compile(
    r"(?P<tests>\d{3,6})\s+tests(?:,\s*(?P<coverage>\d{1,3}(?:\.\d{1,2})?)%\s+coverage)?"
)


class LintFinding(BaseModel):
    """Structured finding emitted by lint checks."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    severity: Literal["error", "warning", "info"] = Field(
        description="Finding severity level"
    )
    check: str = Field(description="Stable check identifier")
    message: str = Field(description="Human-readable finding message")
    file: str | None = Field(default=None, description="Path related to finding")
    line: int | None = Field(default=None, ge=1, description="1-based line number")


class LintCheck(Protocol):
    """Contract for a memory-bank lint check."""

    name: str

    def run(self, project_root: Path) -> list[LintFinding]:
        """Run check and return findings."""
        ...


class _PlanReference(BaseModel):
    """Roadmap plan reference parsed from one line."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    raw_path: str = Field(description="Plan path as written in roadmap")
    line: int = Field(ge=1, description="1-based line index in roadmap")


class _CodeClaimSpec(BaseModel):
    """One configured code-claim assertion."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="Path to source claim file")
    pattern: str = Field(description="Regex pattern used to find claim")
    verify_against: str = Field(description="Path to verification target file")


class _LintConfig(BaseModel):
    """Subset of lint config used by CodeClaimCheck."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    code_claim_checks: list[_CodeClaimSpec] = []
    stale_threshold_days: int = Field(default=30, ge=1)
    stale_test_count_threshold: int = Field(default=200, ge=1)


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a file path."""
    return path.read_text(encoding="utf-8")


def _plans_root(project_root: Path) -> Path:
    """Return .cortex/plans root for this project."""
    return get_cortex_path(project_root, CortexResourceType.PLANS)


def _roadmap_path(project_root: Path) -> Path:
    """Return .cortex/memory-bank/roadmap.md path."""
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK) / "roadmap.md"


def _wiki_root(project_root: Path) -> Path:
    """Return wiki root for this project (same as ``get_cortex_path(..., WIKI)``)."""
    return get_cortex_path(project_root, CortexResourceType.WIKI)


def _memory_bank_root(project_root: Path) -> Path:
    """Return `.cortex/memory-bank` root for this project."""
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)


def _lint_config_path(project_root: Path) -> Path:
    """Return `.cortex/config/lint-config.json` path for this project."""
    return (
        get_cortex_path(project_root, CortexResourceType.CORTEX_DIR)
        / "config"
        / "lint-config.json"
    )


def load_lint_config(project_root: Path) -> _LintConfig | None:
    """Load optional `.cortex/config/lint-config.json` and validate schema."""
    config_path = _lint_config_path(project_root)
    if not config_path.exists():
        return None
    try:
        return _LintConfig.model_validate_json(_read_text(config_path))
    except ValueError:
        return None


def _resolve_project_relative_path(project_root: Path, raw_path: str) -> Path:
    """Resolve relative-to-project path from config entry."""
    normalized = raw_path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith(".cortex/"):
        normalized = normalized[len(".cortex/") :]
        return get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / normalized
    return project_root / normalized


def _extract_section(content: str, *, heading: str) -> tuple[str, int] | None:
    """Return markdown section body and first content line number."""
    lines = content.splitlines()
    start_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            start_idx = idx
            break
    if start_idx is None:
        return None

    content_start = start_idx + 1
    while content_start < len(lines) and not lines[content_start].strip():
        content_start += 1
    content_end = len(lines)
    for idx in range(content_start, len(lines)):
        if _H2_HEADING_PATTERN.match(lines[idx]):
            content_end = idx
            break
    section_text = "\n".join(lines[content_start:content_end]).strip()
    if not section_text:
        return None
    return section_text, content_start + 1


def _parse_latest_quality_snapshot(
    project_root: Path,
) -> tuple[int, float | None] | None:
    """Read most recent detached quality result from `.cortex/.session`."""
    session_dir = (
        get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / ".session"
    )
    if not session_dir.exists():
        return None

    candidates = sorted(
        session_dir.glob("pre_commit_result_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        try:
            payload: object = json.loads(_read_text(candidate))
        except ValueError:
            continue
        snapshot = _extract_quality_snapshot(payload)
        if snapshot is not None:
            return snapshot
    return None


def _extract_quality_snapshot(payload: object) -> tuple[int, float | None] | None:
    """Extract test/coverage values from one detached quality payload."""
    if not isinstance(payload, dict):
        return None
    payload_dict = cast(dict[str, object], payload)
    results_obj = payload_dict.get("results")
    if not isinstance(results_obj, dict):
        return None
    results_dict = cast(dict[str, object], results_obj)
    tests_obj = results_dict.get("tests")
    if not isinstance(tests_obj, dict):
        return None
    tests_dict = cast(dict[str, object], tests_obj)
    tests_run_obj = tests_dict.get("tests_run")
    if not isinstance(tests_run_obj, int) or tests_run_obj <= 0:
        return None
    coverage_obj = tests_dict.get("coverage")
    coverage_value = (
        float(coverage_obj) if isinstance(coverage_obj, int | float) else None
    )
    return tests_run_obj, coverage_value


def _normalize_plan_ref(raw_path: str) -> Path:
    """Normalize roadmap Plan path into path relative to .cortex/plans."""
    trimmed = raw_path.strip().rstrip(".,)")
    if trimmed.startswith(".cortex/plans/"):
        return Path(trimmed[len(".cortex/plans/") :])
    if trimmed.startswith("cortex/plans/"):
        return Path(trimmed[len("cortex/plans/") :])
    if trimmed.startswith("plans/"):
        return Path(trimmed[len("plans/") :])
    return Path(trimmed)


def _extract_plan_references(roadmap_content: str) -> list[_PlanReference]:
    """Return `Plan:` references found in roadmap lines."""
    references: list[_PlanReference] = []
    for line_num, line in enumerate(roadmap_content.splitlines(), start=1):
        marker_index = line.find(_PLAN_PATH_PATTERN)
        if marker_index < 0:
            continue
        path_part = line[marker_index + len(_PLAN_PATH_PATTERN) :].strip()
        if not path_part:
            continue
        normalized_path_part = path_part
        markdown_match = _MARKDOWN_LINK_PATH_PATTERN.search(path_part)
        if markdown_match is not None:
            normalized_path_part = markdown_match.group(1)
        raw_path = normalized_path_part.strip().split()[0].strip("<>")
        if not raw_path:
            continue
        references.append(_PlanReference(raw_path=raw_path, line=line_num))
    return references


def _list_non_archived_plans(project_root: Path) -> list[Path]:
    """List `.md` plan paths relative to `.cortex/plans`, excluding archive."""
    plans_root = _plans_root(project_root)
    if not plans_root.exists():
        return []
    archive_dir_name = Path(CortexResourceType.PLANS_ARCHIVE.value).name
    results: list[Path] = []
    for plan_path in plans_root.rglob("*.md"):
        relative = plan_path.relative_to(plans_root)
        if archive_dir_name in relative.parts:
            continue
        results.append(relative)
    return sorted(results)


class OrphanedPlansCheck:
    """Find plan files not referenced by roadmap `Plan:` entries."""

    name = "orphaned_plans"

    def run(self, project_root: Path) -> list[LintFinding]:
        roadmap = _roadmap_path(project_root)
        if not roadmap.exists():
            return []
        referenced = {
            _normalize_plan_ref(ref.raw_path)
            for ref in _extract_plan_references(_read_text(roadmap))
        }
        findings: list[LintFinding] = []
        for relative_plan in _list_non_archived_plans(project_root):
            if relative_plan in referenced:
                continue
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=f"Plan is not referenced in roadmap: .cortex/plans/{relative_plan}",
                    file=f".cortex/plans/{relative_plan}",
                    line=None,
                )
            )
        return findings


class MissingPlanFilesCheck:
    """Find roadmap `Plan:` references whose target file is missing."""

    name = "missing_plan_files"

    def run(self, project_root: Path) -> list[LintFinding]:
        roadmap = _roadmap_path(project_root)
        if not roadmap.exists():
            return []
        findings: list[LintFinding] = []
        for ref in _extract_plan_references(_read_text(roadmap)):
            relative_plan = _normalize_plan_ref(ref.raw_path)
            target = _plans_root(project_root) / relative_plan
            if target.exists():
                continue
            findings.append(
                LintFinding(
                    severity="error",
                    check=self.name,
                    message=f"Roadmap references missing plan file: {ref.raw_path.rstrip('.,)')}",
                    file=".cortex/memory-bank/roadmap.md",
                    line=ref.line,
                )
            )
        return findings


def _extract_iso_dates_with_lines(content: str) -> list[tuple[str, int]]:
    """Extract unique ISO dates with first-seen line numbers."""
    dates: list[tuple[str, int]] = []
    seen: set[str] = set()
    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in _DATE_PATTERN.finditer(line):
            date_text = match.group(1)
            if date_text in seen:
                continue
            seen.add(date_text)
            dates.append((date_text, line_num))
    return dates


def _parse_iso_date(date_text: str) -> datetime | None:
    """Parse `YYYY-MM-DD` into UTC midnight datetime."""
    try:
        parsed = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC)


class StaleActiveContextCheck:
    """Find stale activeContext dates not represented in progress.md."""

    name = "stale_active_context"

    def __init__(self, stale_threshold_days: int = 30) -> None:
        self._stale_threshold_days = stale_threshold_days

    def _is_stale_without_progress(
        self,
        *,
        date_text: str,
        parsed_date: datetime | None,
        now_utc: datetime,
        progress_content: str,
    ) -> bool:
        if parsed_date is None:
            return False
        threshold = timedelta(days=self._stale_threshold_days)
        if now_utc - parsed_date <= threshold:
            return False
        return date_text not in progress_content

    def _build_finding(self, date_text: str, line_num: int) -> LintFinding:
        return LintFinding(
            severity="warning",
            check=self.name,
            message=(
                "Stale activeContext entry date has no matching progress entry: "
                f"{date_text}"
            ),
            file=".cortex/memory-bank/activeContext.md",
            line=line_num,
        )

    def run(self, project_root: Path) -> list[LintFinding]:
        memory_bank_root = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        active_context = memory_bank_root / "activeContext.md"
        progress = memory_bank_root / "progress.md"
        if not active_context.exists() or not progress.exists():
            return []

        now_utc = datetime.now(UTC)
        progress_content = _read_text(progress)
        findings: list[LintFinding] = []
        for date_text, line_num in _extract_iso_dates_with_lines(
            _read_text(active_context)
        ):
            parsed_date = _parse_iso_date(date_text)
            if not self._is_stale_without_progress(
                date_text=date_text,
                parsed_date=parsed_date,
                now_utc=now_utc,
                progress_content=progress_content,
            ):
                continue
            findings.append(self._build_finding(date_text=date_text, line_num=line_num))
        return findings


class CrossRefCheck:
    """Find references to wiki pages whose files do not exist."""

    name = "cross_ref"

    def _existing_wiki_pages(self, wiki_root: Path) -> set[str]:
        existing: set[str] = set()
        for page in wiki_root.rglob("*.md"):
            existing.add(page.relative_to(wiki_root).as_posix())
        return existing

    def _iter_references(self, content: str) -> list[tuple[str, int]]:
        references: list[tuple[str, int]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            for match in _WIKI_LINK_PATTERN.finditer(line):
                target = match.group(1) or match.group(2)
                if not target:
                    continue
                normalized = target.strip().replace("\\", "/")
                if not normalized or normalized.startswith(
                    ("http://", "https://", "#")
                ):
                    continue
                if normalized.startswith("/"):
                    normalized = normalized[1:]
                if not normalized.endswith(".md"):
                    normalized = f"{normalized}.md"
                references.append((normalized, line_num))
        return references

    def run(self, project_root: Path) -> list[LintFinding]:
        wiki_root = _wiki_root(project_root)
        if not wiki_root.exists():
            return []
        existing = self._existing_wiki_pages(wiki_root)
        findings: list[LintFinding] = []
        for source_file in wiki_root.rglob("*.md"):
            rel_file = source_file.relative_to(project_root).as_posix()
            for target, line_num in self._iter_references(_read_text(source_file)):
                if target in existing:
                    continue
                findings.append(
                    LintFinding(
                        severity="warning",
                        check=self.name,
                        message=f"Wiki reference points to missing page: {target}",
                        file=rel_file,
                        line=line_num,
                    )
                )
        return findings


class IndexStalenessCheck:
    """Find wiki pages that are missing from the wiki catalog table."""

    name = "index_staleness"

    @staticmethod
    def _is_catalog_page(rel_posix: str) -> bool:
        if rel_posix in WIKI_ROOT_DOCUMENT_NAMES:
            return False
        if rel_posix.startswith(f"{WikiCategoryDir.SOURCES.value}/"):
            return False
        return rel_posix.endswith(".md")

    def run(self, project_root: Path) -> list[LintFinding]:
        wiki_root = _wiki_root(project_root)
        if not wiki_root.is_dir():
            return []
        index_path = wiki_root / WikiRootDocument.INDEX.value
        index_text = _read_text(index_path) if index_path.is_file() else ""
        listed = index_catalog_linked_page_paths(index_text)
        findings: list[LintFinding] = []
        for page in sorted(wiki_root.rglob("*.md")):
            rel = page.relative_to(wiki_root).as_posix()
            if not self._is_catalog_page(rel):
                continue
            if rel in listed:
                continue
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=(
                        "Wiki page missing from "
                        f"{WikiRootDocument.INDEX.value} catalog: {rel}"
                    ),
                    file=page.relative_to(project_root).as_posix(),
                    line=None,
                )
            )
        return findings


class CodeClaimCheck:
    """Validate configured claims in docs against source-of-truth files."""

    name = "code_claim"

    def _extract_claim_value(
        self,
        *,
        line: str,
        line_num: int,
    ) -> tuple[str, str, int] | None:
        match = _CLAIM_PATTERN_GROUP.search(line)
        if match is None:
            return None
        key = match.group("key").strip()
        value = match.group("value").strip()
        if not key or not value:
            return None
        return key, value, line_num

    def _claims_from_file(
        self,
        *,
        claim_path: Path,
        pattern: re.Pattern[str],
    ) -> list[tuple[str, str, int]]:
        claims: list[tuple[str, str, int]] = []
        for line_num, line in enumerate(_read_text(claim_path).splitlines(), start=1):
            if pattern.search(line) is None:
                continue
            parsed = self._extract_claim_value(
                line=line,
                line_num=line_num,
            )
            if parsed is None:
                continue
            claims.append(parsed)
        return claims

    def _actual_values(self, verify_path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in _read_text(verify_path).splitlines():
            parsed = self._extract_claim_value(
                line=line,
                line_num=1,
            )
            if parsed is None:
                continue
            key, value, _ = parsed
            values[key] = value
        return values

    def _mismatch_finding(
        self,
        *,
        key: str,
        expected_value: str,
        actual_value: str,
        claim_file: str,
        line_num: int,
    ) -> LintFinding:
        return LintFinding(
            severity="warning",
            check=self.name,
            message=(
                "Claim value does not match verification file for "
                f"'{key}': expected '{expected_value}', actual '{actual_value}'"
            ),
            file=claim_file,
            line=line_num,
        )

    def _resolve_claim_paths(
        self, *, claim_spec: _CodeClaimSpec, project_root: Path
    ) -> tuple[Path, Path] | None:
        claim_path = _resolve_project_relative_path(project_root, claim_spec.file)
        verify_path = _resolve_project_relative_path(
            project_root, claim_spec.verify_against
        )
        if not claim_path.exists() or not verify_path.exists():
            return None
        return claim_path, verify_path

    def _findings_for_spec(
        self, *, claim_spec: _CodeClaimSpec, project_root: Path
    ) -> list[LintFinding]:
        resolved_paths = self._resolve_claim_paths(
            claim_spec=claim_spec, project_root=project_root
        )
        if resolved_paths is None:
            return []
        claim_path, verify_path = resolved_paths
        pattern = re.compile(claim_spec.pattern)
        actual_values = self._actual_values(verify_path)
        findings: list[LintFinding] = []
        for key, expected_value, line_num in self._claims_from_file(
            claim_path=claim_path, pattern=pattern
        ):
            actual_value = actual_values.get(key)
            if actual_value is None or actual_value == expected_value:
                continue
            findings.append(
                self._mismatch_finding(
                    key=key,
                    expected_value=expected_value,
                    actual_value=actual_value,
                    claim_file=claim_spec.file,
                    line_num=line_num,
                )
            )
        return findings

    def run(self, project_root: Path) -> list[LintFinding]:
        config = load_lint_config(project_root)
        if config is None or not config.code_claim_checks:
            return []

        findings: list[LintFinding] = []
        for claim_spec in config.code_claim_checks:
            findings.extend(
                self._findings_for_spec(
                    claim_spec=claim_spec, project_root=project_root
                )
            )
        return findings


class StaleNumericClaimCheck:
    """Warn when `progress.md` What Works test count drifts from quality output."""

    name = "stale_numeric_claim"

    def _finding(
        self,
        *,
        tests_claim: int,
        tests_actual: int,
        threshold: int,
        line_num: int,
    ) -> LintFinding:
        return LintFinding(
            severity="warning",
            check=self.name,
            message=(
                "What Works test-count claim is stale: "
                f"{tests_claim} tests vs latest quality result {tests_actual} tests "
                f"(allowed drift <= {threshold})"
            ),
            file=".cortex/memory-bank/progress.md",
            line=line_num,
        )

    def _extract_claim(self, project_root: Path) -> tuple[int, int] | None:
        progress_path = _memory_bank_root(project_root) / "progress.md"
        if not progress_path.exists():
            return None
        section = _extract_section(
            _read_text(progress_path), heading=_WHAT_WORKS_HEADING
        )
        if section is None:
            return None
        section_text, section_line_num = section
        claim_match = _TEST_COVERAGE_CLAIM_PATTERN.search(section_text)
        if claim_match is None:
            return None
        return int(claim_match.group("tests")), section_line_num

    def run(self, project_root: Path) -> list[LintFinding]:
        claim = self._extract_claim(project_root)
        if claim is None:
            return []
        tests_claim, section_line_num = claim

        quality_snapshot = _parse_latest_quality_snapshot(project_root)
        if quality_snapshot is None:
            return []
        tests_actual, _ = quality_snapshot
        config = load_lint_config(project_root)
        configured_threshold = (
            200 if config is None else config.stale_test_count_threshold
        )
        percent_threshold = int(round(tests_actual * 0.10))
        effective_threshold = max(configured_threshold, percent_threshold)
        if abs(tests_actual - tests_claim) <= effective_threshold:
            return []

        return [
            self._finding(
                tests_claim=tests_claim,
                tests_actual=tests_actual,
                threshold=effective_threshold,
                line_num=section_line_num,
            )
        ]
