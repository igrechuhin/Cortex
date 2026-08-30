"""Plan dependency graph, upstream resolution, and artifact graph computation."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models._enums import PlanExecutionMode, PlanStatus
from cortex.core.pydantic_extra import EXTRA_FORBID

_DEPENDS_RE = re.compile(
    r"^depends_on\s*:\s*\[(.*?)\]\s*$", re.IGNORECASE | re.MULTILINE
)
# AI: quotes optional and no end anchor so `status: "DONE"` and legacy
# `status: "Completed (26-05-04)"` still resolve instead of silently
# defaulting to PENDING.
_STATUS_RE = re.compile(
    r"^status\s*:\s*[\"']?([A-Za-z_]+)", re.IGNORECASE | re.MULTILINE
)
_EXECUTION_RE = re.compile(
    r"^execution\s*:\s*[\"']?([A-Za-z_]+)", re.IGNORECASE | re.MULTILINE
)
# AI: legacy spellings that predate the PlanStatus enum.
_STATUS_ALIASES: dict[str, PlanStatus] = {
    "COMPLETE": PlanStatus.DONE,
    "COMPLETED": PlanStatus.DONE,
}


class PlanNode(BaseModel):
    """Single plan vertex with declared metadata and computed blockers."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    slug: str = Field(description="Plan slug (filename without .md)")
    depends_on: list[str] = Field(
        default_factory=list,
        description="Declared dependency slugs from frontmatter",
    )
    status: PlanStatus = Field(description="Declared status from frontmatter")
    execution: PlanExecutionMode = Field(
        default=PlanExecutionMode.AGENT,
        description="Who executes the plan, from frontmatter ``execution``",
    )
    blocked_by: list[str] = Field(
        default_factory=list,
        description="Dependencies that are not DONE (computed)",
    )


def _empty_edge_list() -> list[tuple[str, str]]:
    return []


def _empty_str_list() -> list[str]:
    return []


def _empty_cycle_list() -> list[list[str]]:
    return []


class ArtifactGraph(BaseModel):
    """Directed dependency view over plan files under a directory."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    nodes: dict[str, PlanNode] = Field(description="Plan slug → node metadata")
    edges: list[tuple[str, str]] = Field(
        default_factory=_empty_edge_list,
        description="Directed edges dependent → dependency",
    )
    ready: list[str] = Field(
        default_factory=_empty_str_list,
        description="Non-DONE plans with no outstanding dependency work",
    )
    blocked: list[str] = Field(
        default_factory=_empty_str_list,
        description="Non-DONE plans blocked by at least one dependency",
    )
    cycles: list[list[str]] = Field(
        default_factory=_empty_cycle_list,
        description="Strongly connected components with cyclic dependency",
    )


PlanMetadata = PlanNode


def normalize_plan_slug(token: str) -> str:
    """Return a bare plan slug from a raw ``depends_on`` entry.

    Tolerates the two forms that used to silently resolve to nothing: a
    trailing ``.md`` extension and a directory prefix such as
    ``.cortex/plans/``. Both would otherwise be looked up as
    ``<plans_dir>/<token>.md`` and never match a file.
    """
    slug = token.strip().strip("\"'").replace("\\", "/").rsplit("/", 1)[-1]
    if slug.endswith(".md"):
        slug = slug[: -len(".md")]
    return slug


def _parse_depends_on(plan_content: str) -> list[str]:
    match = _DEPENDS_RE.search(plan_content)
    if match is None:
        return []
    raw = match.group(1).strip()
    if not raw:
        return []
    deps: list[str] = []
    for item in raw.split(","):
        token = normalize_plan_slug(item)
        if token:
            deps.append(token)
    return deps


def resolve_plan_status_token(raw: str) -> PlanStatus | None:
    """Return the canonical status for a raw frontmatter token, or None."""
    token = raw.strip().strip("\"'").upper()
    for candidate in PlanStatus:
        if candidate.value == token:
            return candidate
    return _STATUS_ALIASES.get(token)


def _parse_plan_status(plan_content: str) -> PlanStatus:
    match = _STATUS_RE.search(plan_content)
    if match is None:
        return PlanStatus.PENDING
    return resolve_plan_status_token(match.group(1)) or PlanStatus.PENDING


def _parse_plan_execution(plan_content: str) -> PlanExecutionMode:
    match = _EXECUTION_RE.search(plan_content)
    if match is None:
        return PlanExecutionMode.AGENT
    raw = match.group(1).strip().lower()
    for candidate in PlanExecutionMode:
        if candidate.value == raw:
            return candidate
    return PlanExecutionMode.AGENT


def read_plan_execution_from_content(plan_content: str) -> PlanExecutionMode:
    """Return declared ``execution`` from YAML frontmatter (default ``agent``)."""
    return _parse_plan_execution(plan_content)


def read_plan_status_from_content(plan_content: str) -> PlanStatus:
    """Return declared ``status`` from YAML frontmatter (default ``PENDING``)."""
    return _parse_plan_status(plan_content)


def _is_done_plan(plan_content: str) -> bool:
    return _parse_plan_status(plan_content) == PlanStatus.DONE


def resolve_upstream_plans(plan_slug: str, plans_dir: Path) -> list[str]:
    """Resolve transitive DONE dependencies in topological order."""
    resolved: list[str] = []
    visited: set[str] = set()

    def visit(slug: str) -> None:
        if slug in visited:
            return
        visited.add(slug)
        plan_path = plans_dir / f"{slug}.md"
        if not plan_path.is_file():
            return
        content = plan_path.read_text(encoding="utf-8")
        for dep in _parse_depends_on(content):
            visit(dep)
        if slug != plan_slug and _is_done_plan(content):
            resolved.append(slug)

    visit(plan_slug)
    return resolved


def _iter_plan_files(
    plans_dir: Path, *, include_archive: bool
) -> list[tuple[str, Path]]:
    if not plans_dir.is_dir():
        return []
    rows: list[tuple[str, Path]] = []
    for path in plans_dir.rglob("*.md"):
        if not path.is_file():
            continue
        rel = path.relative_to(plans_dir)
        if not include_archive and "archive" in rel.parts:
            continue
        rows.append((path.stem, path))
    rows.sort(key=lambda item: (str(item[1]), item[0]))
    return rows


def list_plan_slug_paths(
    plans_dir: Path, *, include_archive: bool = False
) -> list[tuple[str, Path]]:
    """Return sorted ``(slug, path)`` pairs for plan markdown under ``plans_dir``."""
    return _iter_plan_files(plans_dir, include_archive=include_archive)


class _TarjanContext:
    """Mutable state for Tarjan SCC extraction (dependent → dependency edges)."""

    def __init__(self, nodes: set[str], adj: dict[str, list[str]]) -> None:
        self.nodes = nodes
        self.adj = adj
        self.index_counter = 0
        self.stack: list[str] = []
        self.on_stack: set[str] = set()
        self.index: dict[str, int] = {}
        self.lowlink: dict[str, int] = {}
        self.sccs: list[list[str]] = []

    def visit(self, v: str) -> None:
        self.index[v] = self.index_counter
        self.lowlink[v] = self.index_counter
        self.index_counter += 1
        self.stack.append(v)
        self.on_stack.add(v)
        for w in self.adj.get(v, ()):
            if w not in self.nodes:
                continue
            if w not in self.index:
                self.visit(w)
                self.lowlink[v] = min(self.lowlink[v], self.lowlink[w])
            elif w in self.on_stack:
                self.lowlink[v] = min(self.lowlink[v], self.index[w])
        if self.lowlink[v] != self.index[v]:
            return
        comp: list[str] = []
        while True:
            w = self.stack.pop()
            self.on_stack.remove(w)
            comp.append(w)
            if w == v:
                break
        self.sccs.append(comp)

    def run(self) -> list[list[str]]:
        for n in sorted(self.nodes):
            if n not in self.index:
                self.visit(n)
        return self.sccs


def _filter_cyclic_sccs(
    sccs: list[list[str]], adj: dict[str, list[str]]
) -> list[list[str]]:
    """Keep SCCs that contain a directed cycle (length > 1 or self-loop)."""
    cyclic: list[list[str]] = []
    for comp in sccs:
        if len(comp) > 1:
            cyclic.append(sorted(comp))
            continue
        only = comp[0]
        nbrs = adj.get(only, [])
        if only in nbrs:
            cyclic.append([only])
    return cyclic


def _tarjan_cyclic_sccs(nodes: set[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """Return SCCs that contain a directed cycle (including self-edges)."""
    ctx = _TarjanContext(nodes, adj)
    raw = ctx.run()
    return _filter_cyclic_sccs(raw, adj)


def _nodes_in_cycles(cycles: list[list[str]]) -> set[str]:
    out: set[str] = set()
    for comp in cycles:
        out.update(comp)
    return out


def _load_raw_nodes_and_edges(
    rows: list[tuple[str, Path]],
) -> tuple[dict[str, PlanNode], list[tuple[str, str]]]:
    nodes: dict[str, PlanNode] = {}
    edges: list[tuple[str, str]] = []
    for slug, path in rows:
        text = path.read_text(encoding="utf-8")
        deps = _parse_depends_on(text)
        status = _parse_plan_status(text)
        nodes[slug] = PlanNode(
            slug=slug,
            depends_on=list(deps),
            status=status,
            execution=_parse_plan_execution(text),
        )
        for dep in deps:
            edges.append((slug, dep))
    return nodes, edges


def _apply_blocked_by(nodes: dict[str, PlanNode]) -> dict[str, PlanNode]:
    done_slugs = {s for s, n in nodes.items() if n.status == PlanStatus.DONE}
    blocked_by_map: dict[str, list[str]] = {}
    for slug, node in nodes.items():
        blockers: list[str] = []
        for dep in node.depends_on:
            if dep not in nodes or dep not in done_slugs:
                blockers.append(dep)
        blocked_by_map[slug] = sorted(set(blockers))
    return {
        s: nodes[s].model_copy(update={"blocked_by": blocked_by_map[s]}) for s in nodes
    }


def _internal_dep_adjacency(nodes: dict[str, PlanNode]) -> dict[str, list[str]]:
    node_slugs = set(nodes)
    adj: dict[str, list[str]] = defaultdict(list)
    for slug, node in nodes.items():
        for dep in node.depends_on:
            if dep in node_slugs:
                adj[slug].append(dep)
    return dict(adj)


def _partition_ready_blocked(
    nodes: dict[str, PlanNode], cyclic_slugs: set[str]
) -> tuple[list[str], list[str]]:
    ready: list[str] = []
    blocked: list[str] = []
    for slug in sorted(nodes):
        node = nodes[slug]
        if node.status == PlanStatus.DONE:
            continue
        if slug in cyclic_slugs:
            blocked.append(slug)
            continue
        if node.blocked_by:
            blocked.append(slug)
        else:
            ready.append(slug)
    return ready, blocked


def plan_slug_in_dependency_cycle(slug: str, graph: ArtifactGraph) -> bool:
    """Return True when ``slug`` participates in a directed dependency cycle."""
    return any(slug in component for component in graph.cycles)


def register_plan_file_status_from_graph(
    *,
    clarification_blocked: bool,
    graph: ArtifactGraph,
    slug: str,
) -> PlanStatus:
    """YAML ``status`` for a plan being registered (dependency + clarification gate)."""
    if clarification_blocked:
        return PlanStatus.BLOCKED
    node = graph.nodes.get(slug)
    if node is not None and node.blocked_by:
        return PlanStatus.BLOCKED
    return PlanStatus.PENDING


def compute_artifact_graph(
    plans_dir: Path,
    *,
    include_archive: bool = True,
) -> ArtifactGraph:
    """Build dependency metadata, readiness, and cycle information for plan files."""
    # AI: Archive inclusion defaults to True because _apply_blocked_by treats an
    # unknown dependency as unsatisfied, so skipping the archive makes completed
    # (status: DONE) dependencies look outstanding. Only surfaces that deliberately
    # enumerate *active* plans pass include_archive=False.
    rows = _iter_plan_files(plans_dir, include_archive=include_archive)
    nodes, edges = _load_raw_nodes_and_edges(rows)
    nodes = _apply_blocked_by(nodes)
    adj = _internal_dep_adjacency(nodes)
    cycles = _tarjan_cyclic_sccs(set(nodes), adj)
    ready, blocked = _partition_ready_blocked(nodes, _nodes_in_cycles(cycles))
    return ArtifactGraph(
        nodes=nodes,
        edges=sorted(edges),
        ready=ready,
        blocked=blocked,
        cycles=cycles,
    )
