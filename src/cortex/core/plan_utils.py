"""Utilities for parsing Cortex plan markdown documents."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator

from cortex.core.models import ClarificationMarker, TaskNode


class PlanValidationError(ValueError):
    """Raised when a plan task graph is inconsistent (cycles, bad references)."""


# AI: Step headings are the contract for the parallel-task-markers plan; optional
# ``[P]`` / ``[P:after=…]`` only appear immediately before ``Step N:``.
_STEP_HEADING_RE = re.compile(
    r"(?m)^(#{3,})\s+(?:\[(?P<par_marker>P(?::after=(?P<after>[\d,\s]+))?)\]\s+)?Step\s+(?P<step_id>\d+)\s*:\s*(?P<title>[^\n]*?)\s*$"
)

# AI: Single compiled pattern keeps scans fast and documents the exact marker grammar.
_MARKER_PATTERN = re.compile(
    r"\[NEEDS CLARIFICATION(?P<blocking>\(blocking\))?\s*:\s*(?P<reason>[^\]]*)\]",
    re.IGNORECASE,
)


def _fenced_code_spans(text: str) -> list[tuple[int, int]]:
    """Return half-open character spans that lie inside fenced ``` blocks."""
    lines = text.splitlines(keepends=True)
    spans: list[tuple[int, int]] = []
    offset = 0
    in_fence = False
    span_start = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                span_start = offset
            else:
                in_fence = False
                spans.append((span_start, offset + len(line)))
        offset += len(line)
    return spans


def _in_fenced_block(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _line_number_at(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _iter_marker_matches(text: str) -> Iterator[re.Match[str]]:
    spans = _fenced_code_spans(text)
    for match in _MARKER_PATTERN.finditer(text):
        if _in_fenced_block(match.start(), spans):
            continue
        reason = (match.group("reason") or "").strip()
        if not reason:
            continue
        yield match


def find_clarification_markers(content: str) -> list[ClarificationMarker]:
    """Scan *content* for ``[NEEDS CLARIFICATION ...]`` markers.

    Ignores matches inside fenced code blocks. Markers with an empty reason text
    are skipped. Each returned marker has ``resolved=False``.
    """
    out: list[ClarificationMarker] = []
    for match in _iter_marker_matches(content):
        line_no = _line_number_at(content, match.start())
        blocking = match.group("blocking") is not None
        reason = match.group("reason").strip()
        out.append(
            ClarificationMarker(
                reason=reason,
                blocking=blocking,
                location=f"line {line_no}",
                resolved=False,
            )
        )
    return out


_CLARIFICATIONS_HEADING = re.compile(r"^##\s+Clarifications Needed\s*$")


def strip_clarifications_needed_section(content: str) -> str:
    """Remove a ``## Clarifications Needed`` block through the next ``##`` heading."""
    # AI: Drop prior auto-summary so create/enrich can regenerate without duplicate headings.
    lines = content.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _CLARIFICATIONS_HEADING.match(line.rstrip("\r\n")):
            i += 1
            while i < len(lines) and not re.match(r"^##\s+", lines[i]):
                i += 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _format_clarifications_needed_section(markers: list[ClarificationMarker]) -> str:
    lines = [
        "## Clarifications Needed",
        "",
        "Summary of inline `[NEEDS CLARIFICATION]` markers (auto-generated on create):",
        "",
    ]
    for m in markers:
        # AI: Prefix distinguishes blocking markers without relying on bold in logs.
        prefix = "(blocking) " if m.blocking else ""
        lines.append(f"- {prefix}{m.reason} — {m.location}")
    lines.append("")
    return "\n".join(lines)


def _insert_point_clarifications_section(text: str) -> int:
    """Return the index where the Clarifications Needed section should start."""
    ctx = re.search(r"(?m)^##\s+context\s*$", text)
    if ctx:
        return ctx.start()
    goal = re.search(r"(?m)^##\s+goal\s*$", text)
    if goal:
        start = goal.end()
        rest = text[start:]
        nxt = re.search(r"(?m)^##\s+", rest)
        if nxt:
            return start + nxt.start()
        return len(text)
    # AI: Prefer inserting after YAML front matter when standard headings are absent.
    fm = re.match(r"^---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", text, re.DOTALL)
    if fm:
        return fm.end()
    return 0


def apply_clarifications_summary_to_plan(content: str) -> tuple[str, int]:
    """Strip any prior summary, then insert ``## Clarifications Needed`` when markers exist.

    Returns ``(updated_markdown, marker_count)``. When there are no markers, the
    body is returned with any stale summary section removed.
    """
    stripped = strip_clarifications_needed_section(content)
    markers = find_clarification_markers(stripped)
    if not markers:
        return stripped, 0
    section = _format_clarifications_needed_section(markers)
    pos = _insert_point_clarifications_section(stripped)
    before = stripped[:pos]
    after = stripped[pos:]
    if before and not before.endswith(("\n", "\r")):
        before += "\n"
    return before + section + after, len(markers)


def resolve_clarification_markers(
    content: str, resolved_clarifications: dict[str, str]
) -> tuple[str, int]:
    """Replace markers whose reason appears in ``resolved_clarifications``.

    Matches inside fenced code blocks are ignored. Empty replacement values are
    skipped. Returns ``(updated_markdown, resolved_count)``.
    """
    spans = _fenced_code_spans(content)
    normalized: dict[str, str] = {}
    for reason, replacement in resolved_clarifications.items():
        reason_key = reason.strip()
        replacement_value = replacement.strip()
        if reason_key and replacement_value:
            normalized[reason_key] = replacement_value
    if not normalized:
        return content, 0

    resolved_count = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal resolved_count
        if _in_fenced_block(match.start(), spans):
            return match.group(0)
        reason = (match.group("reason") or "").strip()
        if not reason:
            return match.group(0)
        replacement = normalized.get(reason)
        if replacement is None:
            return match.group(0)
        resolved_count += 1
        return replacement

    return _MARKER_PATTERN.sub(_replace, content), resolved_count


def _parse_after_dependencies(raw: str | None) -> list[int]:
    if raw is None:
        return []
    text = raw.strip()
    if not text:
        raise PlanValidationError("empty [P:after=] dependency list")
    out: list[int] = []
    for part in text.split(","):
        piece = part.strip()
        if not piece:
            raise PlanValidationError("empty entry in [P:after=] dependency list")
        if not piece.isdigit():
            raise PlanValidationError(f"non-integer step id in [P:after=]: {piece!r}")
        out.append(int(piece))
    return out


def _graph_has_cycle(nodes: set[int], edges: list[tuple[int, int]]) -> bool:
    adj: defaultdict[int, list[int]] = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)
    color = {n: 0 for n in nodes}

    def dfs(u: int) -> bool:
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    for n in nodes:
        if color[n] == 0 and dfs(n):
            return True
    return False


def _validate_dependencies(step_ids: set[int], nodes: list[TaskNode]) -> None:
    edges: list[tuple[int, int]] = []
    for node in nodes:
        for dep in node.depends_on:
            if dep not in step_ids:
                raise PlanValidationError(
                    f"step {node.step_id} depends on missing step {dep}"
                )
            edges.append((dep, node.step_id))
    if step_ids and _graph_has_cycle(step_ids, edges):
        raise PlanValidationError("cyclic step dependencies")


def parse_task_graph(plan_content: str) -> list[TaskNode]:
    """Parse implementation ``Step N`` headings into a validated task graph.

    Recognizes optional ``[P]`` and ``[P:after=…]`` markers (see ``TaskNode``).
    Headings inside fenced code blocks are ignored. Raises
    :class:`PlanValidationError` on duplicate step numbers, missing dependency
    targets, or dependency cycles.
    """
    spans = _fenced_code_spans(plan_content)
    seen_ids: set[int] = set()
    raw_nodes: list[TaskNode] = []
    for match in _STEP_HEADING_RE.finditer(plan_content):
        if _in_fenced_block(match.start(), spans):
            continue
        sid = int(match.group("step_id"))
        if sid in seen_ids:
            raise PlanValidationError(f"duplicate Step {sid} heading")
        seen_ids.add(sid)
        title = (match.group("title") or "").strip()
        marker = match.group("par_marker")
        parallel = marker is not None
        depends_on = _parse_after_dependencies(match.group("after")) if parallel else []
        end = match.end()
        nxt = _STEP_HEADING_RE.search(plan_content, pos=end)
        body = plan_content[end : nxt.start()] if nxt else plan_content[end:]
        raw_nodes.append(
            TaskNode(
                step_id=sid,
                title=title,
                parallel=parallel,
                depends_on=depends_on,
                content=body,
            )
        )
    step_ids = {n.step_id for n in raw_nodes}
    _validate_dependencies(step_ids, raw_nodes)
    return raw_nodes


_PATH_IN_BODY = re.compile(r"`(src/[^`\n]+)`|(?<![\w/])(src/[A-Za-z0-9_./-]+)")


def _paths_mentioned_in_plan_segment(segment: str) -> set[str]:
    """Collect ``src/…`` path-like tokens from a step body (backticks or bare)."""
    found: set[str] = set()
    for match in _PATH_IN_BODY.finditer(segment):
        path = match.group(1) or match.group(2)
        path = path.rstrip(".,);:")
        if path.startswith("src/"):
            found.add(path)
    return found


def apply_independence_parallel_markers(plan_content: str) -> str:
    """Insert ``[P]`` on step headings when file footprints are pairwise disjoint.

    # AI: The planner may call ``think()`` before ``plan(create)``; this pass is a
    # deterministic follow-up so clearly file-disjoint steps surface as parallel
    # hints without another MCP round-trip. Steps with no ``src/`` mentions are
    # left sequential to avoid false positives.
    """
    matches = list(_STEP_HEADING_RE.finditer(plan_content))
    if len(matches) < 2:
        return plan_content
    cumulative: set[str] = set()
    replacements: dict[int, str] = {}
    for idx, match in enumerate(matches):
        hashes = match.group(1)
        step_id = int(match.group("step_id"))
        title = (match.group("title") or "").strip()
        marker = match.group("par_marker")
        start_body = match.end()
        next_match = matches[idx + 1] if idx + 1 < len(matches) else None
        end_body = next_match.start() if next_match else len(plan_content)
        body = plan_content[start_body:end_body]
        paths = _paths_mentioned_in_plan_segment(body)
        if step_id > 1 and marker is None and paths and paths.isdisjoint(cumulative):
            replacements[idx] = f"{hashes} [P] Step {step_id}: {title}"
        cumulative |= paths
    if not replacements:
        return plan_content
    parts: list[str] = []
    cursor = 0
    for idx, match in enumerate(matches):
        parts.append(plan_content[cursor : match.start()])
        parts.append(replacements.get(idx, match.group(0)))
        cursor = match.end()
    parts.append(plan_content[cursor:])
    return "".join(parts)


def task_graph_can_parallelize(nodes: list[TaskNode]) -> bool:
    """True when the plan exposes at least one ``[P]`` parallel step."""
    return any(node.parallel for node in nodes)


def _task_nodes_by_id(nodes: list[TaskNode]) -> dict[int, TaskNode]:
    return {n.step_id: n for n in nodes}


def _parallel_implicit_prereqs(by_id: dict[int, TaskNode], step_id: int) -> set[int]:
    # AI: Parallel steps skip prior *parallel* work but never skip a sequential
    # predecessor; those still serialize the document spine.
    return {j for j in by_id if j < step_id and not by_id[j].parallel}


def _sequential_implicit_prereqs(by_id: dict[int, TaskNode], step_id: int) -> set[int]:
    return {j for j in by_id if j < step_id}


def is_task_execution_ready(
    node: TaskNode, completed: set[int], by_id: dict[int, TaskNode]
) -> bool:
    """True when *node* may start given *completed* step ids (half-open frontier)."""
    if node.step_id in completed:
        return False
    if node.parallel:
        implicit = _parallel_implicit_prereqs(by_id, node.step_id)
        return implicit <= completed and set(node.depends_on) <= completed
    implicit = _sequential_implicit_prereqs(by_id, node.step_id)
    return implicit <= completed


def next_execution_frontier(
    nodes: list[TaskNode],
    completed: set[int],
    *,
    max_parallel: int = 3,
) -> list[TaskNode]:
    """Next batch of steps for ``/cortex/do`` parallel dispatch.

    Prefers up to ``max_parallel`` parallel steps that are ready. When none are
    ready, yields at most one ready sequential step. Returns ``[]`` when every
    step id in *nodes* is in *completed* or no step is runnable yet.
    """
    if max_parallel < 1:
        max_parallel = 1
    by_id = _task_nodes_by_id(nodes)
    parallel_ready = sorted(
        (
            n
            for n in nodes
            if n.parallel and is_task_execution_ready(n, completed, by_id)
        ),
        key=lambda n: n.step_id,
    )
    if parallel_ready:
        return parallel_ready[:max_parallel]
    sequential_ready = sorted(
        (
            n
            for n in nodes
            if not n.parallel and is_task_execution_ready(n, completed, by_id)
        ),
        key=lambda n: n.step_id,
    )
    return sequential_ready[:1]
