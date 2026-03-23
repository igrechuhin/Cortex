"""Performance assertions for token counting (tiktoken + in-process hash cache).

Targets align with `.cortex/plans/preflight-performance-profiling.md`: warm
hash-cache hits should stay well under 5ms median on developer hardware.
"""

import importlib.util
import statistics
import time

import pytest

from cortex.core.token_counter import TokenCounter

_TIKTOKEN_INSTALLED = importlib.util.find_spec("tiktoken") is not None


def _large_document(counter: TokenCounter, min_tokens: int) -> str:
    """Build UTF-8 text with at least ``min_tokens`` tiktoken tokens."""
    chunk = "perfbench " * 500
    text = chunk
    while counter.count_tokens(text) < min_tokens:
        text += chunk
    return text


@pytest.mark.skipif(
    not _TIKTOKEN_INSTALLED,
    reason="tiktoken not installed; see: productContext.md#success-metrics",
)
def test_token_counter_cold_large_document_token_count() -> None:
    """Cold path: first encode of a ~5k-token document succeeds with expected scale."""
    counter = TokenCounter()
    if counter.encoding is None:
        pytest.skip(
            "tiktoken encoding unavailable; see: productContext.md#success-metrics"
        )
    text = _large_document(counter, 5000)
    fresh = TokenCounter()
    if fresh.encoding is None:
        pytest.skip(
            "tiktoken encoding unavailable; see: productContext.md#success-metrics"
        )
    token_total = fresh.count_tokens(text)
    assert token_total >= 5000


@pytest.mark.skipif(
    not _TIKTOKEN_INSTALLED,
    reason="tiktoken not installed; see: productContext.md#success-metrics",
)
def test_token_counter_warm_cache_median_under_5ms() -> None:
    """Warm path: repeated ``count_tokens_with_cache`` median stays under 5ms."""
    counter = TokenCounter()
    if counter.encoding is None:
        pytest.skip(
            "tiktoken encoding unavailable; see: productContext.md#success-metrics"
        )
    text = _large_document(counter, 5000)
    content_hash = counter.content_hash(text)
    _ = counter.count_tokens_with_cache(text, content_hash)

    samples: list[float] = []
    for _ in range(25):
        start = time.perf_counter()
        _ = counter.count_tokens_with_cache(text, content_hash)
        samples.append(time.perf_counter() - start)

    median_seconds = statistics.median(samples)
    p95_seconds = sorted(samples)[int(len(samples) * 0.95)]
    assert (
        median_seconds < 0.005
    ), f"median warm cache latency {median_seconds * 1000:.2f}ms exceeds 5ms target"
    assert (
        p95_seconds < 0.020
    ), f"p95 warm cache latency {p95_seconds * 1000:.2f}ms exceeds 20ms target"
