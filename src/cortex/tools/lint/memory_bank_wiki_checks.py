"""Wiki-link lint checks extracted from memory_bank_lint_checks."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.lint.memory_bank_lint_checks import LintFinding
from cortex.wiki.wiki_root_files import WikiRootDocument

_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]|\[[^\]]+\]\(([^)]+)\)")
_SOURCE_PATH_PATTERN = re.compile(
    r"(?:\.cortex/memory-bank/)?sources/(?P<slug>[a-zA-Z0-9._-]+)\.md"
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class OrphanedWikiPagesCheck:
    """Find wiki pages without inbound links from wiki or memory-bank files."""

    name = "orphaned_wiki_pages"

    def _normalize_target(self, target: str) -> str | None:
        normalized = target.strip().replace("\\", "/")
        if not normalized or normalized.startswith(("http://", "https://", "#")):
            return None
        if normalized.startswith("/"):
            normalized = normalized[1:]
        if not normalized.endswith(".md"):
            normalized = f"{normalized}.md"
        return normalized

    def _iter_targets(self, content: str) -> list[str]:
        targets: list[str] = []
        for line in content.splitlines():
            for match in _WIKI_LINK_PATTERN.finditer(line):
                raw_target = match.group(1) or match.group(2)
                if not raw_target:
                    continue
                normalized = self._normalize_target(raw_target)
                if normalized is not None:
                    targets.append(normalized)
        return targets

    def _memory_bank_sources(self, project_root: Path) -> list[Path]:
        memory_bank_root = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        if not memory_bank_root.exists():
            return []
        return sorted(memory_bank_root.rglob("*.md"))

    def _collect_inbound_links(
        self, project_root: Path, wiki_root: Path, wiki_pages: list[Path]
    ) -> tuple[set[str], set[str]]:
        existing_pages = {page.relative_to(wiki_root).as_posix() for page in wiki_pages}
        inbound_links: set[str] = set()
        wiki_pages_with_outbound_links: set[str] = set()
        for wiki_page in wiki_pages:
            relative_source = wiki_page.relative_to(wiki_root).as_posix()
            for target in self._iter_targets(_read_text(wiki_page)):
                if target in existing_pages:
                    wiki_pages_with_outbound_links.add(relative_source)
                    inbound_links.add(target)
        for memory_bank_file in self._memory_bank_sources(project_root):
            for target in self._iter_targets(_read_text(memory_bank_file)):
                if target in existing_pages:
                    inbound_links.add(target)
        return inbound_links, wiki_pages_with_outbound_links

    def _build_findings(
        self,
        project_root: Path,
        wiki_root: Path,
        wiki_pages: list[Path],
        inbound_links: set[str],
        linked_roots: set[str],
    ) -> list[LintFinding]:
        findings: list[LintFinding] = []
        for wiki_page in wiki_pages:
            relative_page = wiki_page.relative_to(wiki_root).as_posix()
            if (
                relative_page == WikiRootDocument.INDEX.value
                and relative_page in linked_roots
            ):
                continue
            if relative_page in inbound_links:
                continue
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=f"Wiki page has no inbound links: {relative_page}",
                    file=wiki_page.relative_to(project_root).as_posix(),
                    line=None,
                )
            )
        return findings

    def _source_slug_references(self, content: str) -> set[str]:
        return {match.group("slug") for match in _SOURCE_PATH_PATTERN.finditer(content)}

    def _iter_summary_files(self, queries_dir: Path) -> list[Path]:
        if not queries_dir.exists():
            return []
        return sorted(queries_dir.glob("*.md"))

    def _missing_source_findings(
        self,
        *,
        summary_path: Path,
        summary_slugs: set[str],
        sources_dir: Path,
        memory_bank_root: Path,
    ) -> list[LintFinding]:
        findings: list[LintFinding] = []
        for source_slug in summary_slugs:
            source_path = sources_dir / f"{source_slug}.md"
            if source_path.exists():
                continue
            summary_rel = summary_path.relative_to(memory_bank_root).as_posix()
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=(
                        "Summary page references missing ingest source: "
                        f"sources/{source_slug}.md"
                    ),
                    file=f".cortex/memory-bank/{summary_rel}",
                    line=None,
                )
            )
        return findings

    def _orphaned_source_findings(
        self, *, source_slugs: set[str], referenced_slugs: set[str]
    ) -> list[LintFinding]:
        findings: list[LintFinding] = []
        for source_slug in sorted(source_slugs - referenced_slugs):
            findings.append(
                LintFinding(
                    severity="warning",
                    check=self.name,
                    message=(
                        "Ingest source has no corresponding summary page reference: "
                        f"sources/{source_slug}.md"
                    ),
                    file=f".cortex/memory-bank/sources/{source_slug}.md",
                    line=None,
                )
            )
        return findings

    def _source_summary_findings(self, project_root: Path) -> list[LintFinding]:
        memory_bank_root = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        sources_dir = memory_bank_root / "sources"
        queries_dir = memory_bank_root / "queries"
        source_slugs = (
            {source_path.stem for source_path in sources_dir.glob("*.md")}
            if sources_dir.exists()
            else set[str]()
        )
        findings: list[LintFinding] = []
        referenced_slugs: set[str] = set()
        for summary_path in self._iter_summary_files(queries_dir):
            summary_slugs = self._source_slug_references(_read_text(summary_path))
            referenced_slugs.update(summary_slugs)
            findings.extend(
                self._missing_source_findings(
                    summary_path=summary_path,
                    summary_slugs=summary_slugs,
                    sources_dir=sources_dir,
                    memory_bank_root=memory_bank_root,
                )
            )
        findings.extend(
            self._orphaned_source_findings(
                source_slugs=source_slugs, referenced_slugs=referenced_slugs
            )
        )
        return findings

    def run(self, project_root: Path) -> list[LintFinding]:
        findings = self._source_summary_findings(project_root)
        wiki_root = get_cortex_path(project_root, CortexResourceType.WIKI)
        if not wiki_root.exists():
            return findings
        wiki_pages = sorted(wiki_root.rglob("*.md"))
        inbound_links, linked_roots = self._collect_inbound_links(
            project_root, wiki_root, wiki_pages
        )
        findings.extend(
            self._build_findings(
                project_root, wiki_root, wiki_pages, inbound_links, linked_roots
            )
        )
        return findings
