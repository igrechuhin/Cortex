"""Byte-stability regression tests for every published ``cortex://`` resource.

A resource body that differs between two reads of unchanged state invalidates
the host's prompt-cache prefix from that point onward. These tests read each
published resource twice with no intervening state change and assert the bytes
are identical, including with the resource-level TTL caches bypassed so a cache
hit cannot mask real drift.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from typing import cast

import pytest

from cortex.discovery.prompt_prefix import payload_digest
from cortex.discovery.published_inventory import PUBLISHED_STATIC_RESOURCE_URIS


def _resource_text(result: object) -> str:
    """Flatten a FastMCP resource read result into its text payload."""
    # BELIEF: FastMCP's ResourceResult exposes .content; older shapes are
    # directly iterable. Both are handled rather than assumed.
    contents: object = getattr(result, "content", None)
    source: object = result if contents is None else contents
    assert isinstance(source, Iterable)
    parts: list[object] = list(cast(Iterable[object], source))
    return "".join(str(getattr(part, "text", part)) for part in parts)


async def _read(uri: str) -> str:
    from cortex.server import mcp

    _ = importlib.import_module("cortex.tools")
    return _resource_text(await mcp.read_resource(uri))


# AI: cortex://analysis is a live view of usage logs and session state, not a
# cacheable prefix surface: a parallel test worker mutating .cortex/ between the
# two reads makes the body drift for reasons unrelated to rendering determinism.
# Excluded here rather than dropped from PUBLISHED_STATIC_RESOURCE_URIS, which is
# the published-surface inventory the docs drift check reads.
LIVE_STATE_RESOURCE_URIS: frozenset[str] = frozenset({"cortex://analysis"})

STABLE_RESOURCE_URIS = tuple(
    uri for uri in PUBLISHED_STATIC_RESOURCE_URIS if uri not in LIVE_STATE_RESOURCE_URIS
)


@pytest.mark.parametrize("uri", STABLE_RESOURCE_URIS)
async def test_resource_body_identical_on_repeated_read(uri: str) -> None:
    """Two consecutive reads of an unchanged resource are byte-identical."""
    # Arrange / Act
    first = await _read(uri)
    second = await _read(uri)

    # Assert
    assert payload_digest(first) == payload_digest(second), f"{uri} body drifted"


async def test_rules_resource_stable_with_cache_bypassed() -> None:
    """``cortex://rules`` is stable even when its TTL cache cannot mask drift."""
    # Arrange
    from cortex.tools.synapse.rules_operations import invalidate_rules_resource_cache

    # Act
    invalidate_rules_resource_cache()
    first = await _read("cortex://rules")
    invalidate_rules_resource_cache()
    second = await _read("cortex://rules")

    # Assert
    assert first == second


async def test_rules_resource_body_omits_last_indexed() -> None:
    """The volatile ``last_indexed`` field is no longer in the stable body."""
    # Arrange
    from cortex.tools.synapse.rules_operations import invalidate_rules_resource_cache

    # Act
    invalidate_rules_resource_cache()
    body = await _read("cortex://rules")

    # Assert
    assert "last_indexed" not in body


async def test_mutation_guard_reintroduced_timestamp_is_detected() -> None:
    """Injecting a timestamp into a body makes the stability check fail."""
    # Arrange
    body = await _read("cortex://rules")
    mutated = body.replace("{", '{"last_indexed": "2026-08-06T15:57:20.399696",', 1)

    # Act / Assert
    assert payload_digest(body) != payload_digest(mutated)
