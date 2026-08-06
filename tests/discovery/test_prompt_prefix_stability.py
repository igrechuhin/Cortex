"""Byte-stability regression tests for the agent-visible prompt prefix.

The host's prompt cache is an exact-prefix byte match, and tool schemas render
at position zero. These tests lock the property that Cortex contributes
identical bytes across processes; the mutation guard proves they can fail.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cortex.discovery.prompt_prefix import (
    canonical_json,
    payload_digest,
    render_tool_schema_payload,
)
from cortex.discovery.tool_registry import get_known_script_names, get_known_tool_names
from cortex.tools.evaluation._agentic_models import ModelToolSchema

REPO_ROOT = Path(__file__).resolve().parents[2]

_RENDER_SCRIPT = (
    "import asyncio, sys;"
    "from cortex.discovery.prompt_prefix import ("
    "render_tool_schema_payload, payload_digest);"
    "from cortex.tools.evaluation._local_session import ("
    "load_registered_tool_schemas);"
    "sys.stdout.write(payload_digest(render_tool_schema_payload("
    "asyncio.run(load_registered_tool_schemas()))))"
)

_NAMES_SCRIPT = (
    "import sys;"
    "from cortex.discovery.tool_registry import get_known_tool_names;"
    'sys.stdout.write(",".join(get_known_tool_names()))'
)


def _run_with_hash_seed(script: str, seed: str) -> str:
    """Run ``script`` in a subprocess pinned to ``PYTHONHASHSEED=seed``."""
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={
            "PYTHONHASHSEED": seed,
            "PATH": "/usr/bin:/bin",
            "HOME": str(Path.home()),
        },
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


class TestCanonicalJson:
    """Deterministic serialization for agent-visible payloads."""

    def test_key_order_does_not_affect_bytes(self) -> None:
        # Arrange
        first = {"b": 1, "a": {"z": 2, "y": 3}}
        second = {"a": {"y": 3, "z": 2}, "b": 1}

        # Act
        rendered_first = canonical_json(first)
        rendered_second = canonical_json(second)

        # Assert
        assert rendered_first == rendered_second

    def test_digest_is_stable_for_equal_payloads(self) -> None:
        # Arrange
        payload = canonical_json({"a": 1})

        # Act / Assert
        assert payload_digest(payload) == payload_digest(canonical_json({"a": 1}))


class TestRenderToolSchemaPayload:
    """Rendering pins ordering and content."""

    def test_registration_order_does_not_affect_bytes(self) -> None:
        # Arrange
        alpha = ModelToolSchema(name="alpha", description="A", input_schema={"x": 1})
        beta = ModelToolSchema(name="beta", description="B", input_schema={"y": 2})

        # Act
        forward = render_tool_schema_payload([alpha, beta])
        reverse = render_tool_schema_payload([beta, alpha])

        # Assert
        assert forward == reverse

    def test_mutation_guard_injected_timestamp_breaks_stability(self) -> None:
        """A timestamp in a description must make the check fail (it has teeth)."""
        # Arrange
        clean = ModelToolSchema(name="alpha", description="A", input_schema={})
        volatile = ModelToolSchema(
            name="alpha",
            description="A (indexed 2026-08-06T15:57:20.399696)",
            input_schema={},
        )

        # Act
        clean_payload = render_tool_schema_payload([clean])
        volatile_payload = render_tool_schema_payload([volatile])

        # Assert
        assert clean_payload != volatile_payload
        assert payload_digest(clean_payload) != payload_digest(volatile_payload)

    def test_mutation_guard_injected_schema_field_breaks_stability(self) -> None:
        # Arrange
        clean = ModelToolSchema(name="alpha", description="A", input_schema={})
        volatile = ModelToolSchema(
            name="alpha", description="A", input_schema={"session_id": "abc123"}
        )

        # Act / Assert
        assert render_tool_schema_payload([clean]) != render_tool_schema_payload(
            [volatile]
        )


class TestKnownNameOrdering:
    """Ordering accessors are sorted regardless of source order."""

    def test_tool_names_are_sorted(self) -> None:
        # Arrange / Act
        names = get_known_tool_names()

        # Assert
        assert names == sorted(names)

    def test_script_names_are_sorted(self, tmp_path: Path) -> None:
        # Arrange
        scripts_dir = tmp_path / ".cortex" / "synapse" / "scripts" / "python"
        scripts_dir.mkdir(parents=True)
        for stem in ("zeta", "alpha", "middle"):
            _ = (scripts_dir / f"{stem}.py").write_text("", encoding="utf-8")

        # Act
        names = get_known_script_names(tmp_path)

        # Assert
        assert names == ["alpha", "middle", "zeta"]

    def test_tool_names_identical_across_hash_seeds(self) -> None:
        # Arrange / Act
        first = _run_with_hash_seed(_NAMES_SCRIPT, "0")
        second = _run_with_hash_seed(_NAMES_SCRIPT, "12345")

        # Assert
        assert first == second


class TestCrossProcessSchemaStability:
    """The durable deliverable: identical schema bytes across hash seeds."""

    def test_tool_schema_payload_identical_across_hash_seeds(self) -> None:
        # Arrange / Act
        first = _run_with_hash_seed(_RENDER_SCRIPT, "0")
        second = _run_with_hash_seed(_RENDER_SCRIPT, "12345")

        # Assert
        assert first, "renderer produced no output"
        assert first == second
