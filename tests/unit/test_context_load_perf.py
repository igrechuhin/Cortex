"""Timing regression tests for context loading (``load_context_impl``).

Target: median wall time under 100ms for the Cortex repo memory bank
(``productContext.md`` success metrics). Skips when the checkout has no memory bank
(e.g. sparse or partial clones).
"""

import statistics
import time
from pathlib import Path

import pytest

from cortex.managers.initialization import get_managers
from cortex.tools.context.load_operations import load_context_impl

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MEMORY_BANK = _REPO_ROOT / ".cortex" / "memory-bank"
_MEMORY_BANK_READY = _MEMORY_BANK.is_dir() and (
    (_MEMORY_BANK / "projectBrief.md").is_file()
    or (_MEMORY_BANK / "activeContext.md").is_file()
)

requires_cortex_memory_bank = pytest.mark.skipif(
    not _MEMORY_BANK_READY,
    reason=(
        "Requires full Cortex .cortex/memory-bank checkout; "
        "see: productContext.md#success-metrics (<100ms context load target)"
    ),
)


@requires_cortex_memory_bank
@pytest.mark.asyncio
async def test_context_load_meets_100ms_target() -> None:
    """Median ``load_context_impl`` time stays under 100ms after warmup."""
    mgrs = await get_managers(_REPO_ROOT)
    _ = await load_context_impl(
        mgrs,
        task_description="general session context",
        token_budget=50_000,
        strategy="dependency_aware",
        project_root=_REPO_ROOT,
    )

    samples: list[float] = []
    for _ in range(7):
        start = time.perf_counter()
        _ = await load_context_impl(
            mgrs,
            task_description="general session context",
            token_budget=50_000,
            strategy="dependency_aware",
            project_root=_REPO_ROOT,
        )
        samples.append(time.perf_counter() - start)

    median_seconds = statistics.median(samples)
    p95_seconds = sorted(samples)[int(len(samples) * 0.95)]
    assert (
        median_seconds < 0.1
    ), f"median context load {median_seconds * 1000:.1f}ms exceeds 100ms target"
    assert (
        p95_seconds < 0.25
    ), f"p95 context load {p95_seconds * 1000:.1f}ms exceeds 250ms target"
