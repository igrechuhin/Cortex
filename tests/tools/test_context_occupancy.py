"""Tests for the context-usage store, statusline parsing, and producer script.

Session-binding contract: snapshots are per-host-session files; a read
requires the caller's trusted harness session_id (SessionStart hook
capture) and returns data only on an exact match. A bound session never
receives another session's occupancy — not even when the other session's
snapshot is the sole fresh one on disk.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import cast

import pytest

from cortex.tools.session.context_usage_store import (
    ContextUsageSnapshot,
    parse_statusline_payload,
    read_context_usage,
    record_context_usage,
    session_cache_key,
)

REQUIRES_JQ = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="ref: scripts/cortex-context-usage-statusline.sh producer needs jq",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "statusline" / "host-statusline-payload.jsonl"
)
PRODUCER_SCRIPT = REPO_ROOT / "scripts" / "cortex-context-usage-statusline.sh"
HOST_SESSION_ID = "de5dcfb0-9129-4d19-a6ba-686c69abff0e"


def load_host_payload() -> dict[str, object]:
    """Return the first (session-start) payload from the host capture."""
    first_line = HOST_FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    payload: dict[str, object] = json.loads(first_line)
    return payload


def store_path(project_root: Path, session_id: str) -> Path:
    """Absolute path of one session's snapshot file."""
    return project_root / ".cortex" / ".cache" / Path(session_cache_key(session_id))


def session_files(project_root: Path) -> list[Path]:
    """All snapshot files currently on disk, across sessions."""
    directory = project_root / ".cortex" / ".cache" / "session"
    if not directory.is_dir():
        return []
    return sorted(directory.glob("context-usage-*.json"))


def make_snapshot(
    used_tokens: int = 1_000,
    as_of: float | None = None,
    session_id: str = "test-session",
) -> ContextUsageSnapshot:
    """Build a valid fresh snapshot for store tests."""
    return ContextUsageSnapshot(
        session_id=session_id,
        used_tokens=used_tokens,
        limit_tokens=200_000,
        used_percentage=used_tokens / 200_000 * 100,
        as_of=time.time() if as_of is None else as_of,
        source="statusline",
    )


class TestParseStatuslinePayload:
    """Tests for parse_statusline_payload against real and synthetic payloads."""

    def test_host_fixture_parses_with_summed_tokens(self) -> None:
        """Host fixture yields used = total_input + total_output and payload limit."""
        payload = load_host_payload()
        snapshot = parse_statusline_payload(payload, as_of=1_000.0)
        assert snapshot is not None
        context_window_raw = payload["context_window"]
        assert isinstance(context_window_raw, dict)
        context_window = cast("dict[str, object]", context_window_raw)
        total_input = context_window["total_input_tokens"]
        total_output = context_window["total_output_tokens"]
        assert isinstance(total_input, int) and isinstance(total_output, int)
        limit = context_window["context_window_size"]
        assert isinstance(limit, int)
        assert snapshot.used_tokens == total_input + total_output
        assert snapshot.limit_tokens == limit
        assert snapshot.session_id == payload["session_id"]
        assert snapshot.source == "statusline"
        assert snapshot.as_of == 1_000.0

    def test_host_fixture_null_fields_tolerated(self) -> None:
        """Session-start null used_percentage/current_usage never break parsing."""
        payload = load_host_payload()
        context_window_raw = payload["context_window"]
        assert isinstance(context_window_raw, dict)
        context_window = cast("dict[str, object]", context_window_raw)
        assert context_window["used_percentage"] is None
        assert context_window["current_usage"] is None
        snapshot = parse_statusline_payload(payload)
        assert snapshot is not None
        assert snapshot.used_percentage == 0.0

    def test_payload_limit_overrides_default_constant(self) -> None:
        """A payload context_window_size wins over DEFAULT_CONTEXT_WINDOW_TOKENS."""
        snapshot = parse_statusline_payload(
            {
                "session_id": "s",
                "context_window": {
                    "total_input_tokens": 10,
                    "total_output_tokens": 20,
                    "context_window_size": 1_000_000,
                },
            }
        )
        assert snapshot is not None
        assert snapshot.limit_tokens == 1_000_000

    def test_missing_context_window_returns_none(self) -> None:
        """A payload without context_window produces no snapshot."""
        assert parse_statusline_payload({"session_id": "s"}) is None

    def test_non_integer_totals_return_none(self) -> None:
        """String, boolean, null, or float totals are schema drift, not zero."""
        for bad in ("150", True, None, 1.5):
            snapshot = parse_statusline_payload(
                {
                    "session_id": "s",
                    "context_window": {
                        "total_input_tokens": bad,
                        "total_output_tokens": 1,
                    },
                }
            )
            assert snapshot is None

    def test_missing_or_empty_session_id_returns_none(self) -> None:
        """Unattributable payloads (no/empty session_id) produce no snapshot."""
        context_window = {
            "total_input_tokens": 5,
            "total_output_tokens": 6,
        }
        assert parse_statusline_payload({"context_window": context_window}) is None
        assert (
            parse_statusline_payload(
                {"session_id": "", "context_window": context_window}
            )
            is None
        )

    def test_computed_ratio_matches_payload_used_percentage(self) -> None:
        """Computed used/limit ratio cross-checks the harness's own percentage."""
        used_input, used_output, limit = 150_000, 42_000, 200_000
        snapshot = parse_statusline_payload(
            {
                "session_id": "s",
                "context_window": {
                    "total_input_tokens": used_input,
                    "total_output_tokens": used_output,
                    "context_window_size": limit,
                    "used_percentage": 96.0,
                },
            }
        )
        assert snapshot is not None
        assert snapshot.used_tokens == used_input + used_output
        assert snapshot.used_percentage == pytest.approx(96.0)  # type: ignore[arg-type]


class TestSessionCacheKey:
    """Tests for the per-session cache key sanitizer."""

    def test_plain_uuid_keyed_verbatim(self) -> None:
        """A UUID session id maps to its own snapshot filename."""
        assert session_cache_key(HOST_SESSION_ID) == (
            f"session/context-usage-{HOST_SESSION_ID}.json"
        )

    def test_hostile_id_never_becomes_a_path(self) -> None:
        """Traversal-bearing ids flatten to one filename under session/."""
        key = session_cache_key("../../etc/passwd")
        assert Path(key).parts == ("session", Path(key).name)
        assert "/" not in key.removeprefix("session/")
        assert key.startswith("session/context-usage-")


class TestContextUsageStore:
    """Tests for exact-match bound record/read round-trips."""

    async def test_bound_read_roundtrip(self, tmp_path: Path) -> None:
        """A bound session reads back its own recorded snapshot."""
        snapshot = make_snapshot(session_id="s1")
        await record_context_usage(tmp_path, snapshot)
        assert store_path(tmp_path, "s1").exists()
        assert await read_context_usage(tmp_path, "s1") == snapshot

    async def test_unbound_caller_gets_nothing(self, tmp_path: Path) -> None:
        """No trusted binding (None) always yields None, never a guess."""
        await record_context_usage(tmp_path, make_snapshot(session_id="s1"))
        assert await read_context_usage(tmp_path, None) is None

    async def test_bound_session_never_inherits_foreign_sole_snapshot(
        self, tmp_path: Path
    ) -> None:
        """Session B must not read session A's snapshot, even if it is the
        sole fresh one on disk (B opened within A's TTL / B has no producer)."""
        await record_context_usage(
            tmp_path, make_snapshot(used_tokens=199_000, session_id="session-a")
        )
        assert session_files(tmp_path) == [store_path(tmp_path, "session-a")]
        assert await read_context_usage(tmp_path, "session-b") is None

    async def test_latest_wins_within_one_session(self, tmp_path: Path) -> None:
        """A second record for the SAME session replaces the first."""
        await record_context_usage(
            tmp_path, make_snapshot(used_tokens=1_000, session_id="s1")
        )
        await record_context_usage(
            tmp_path, make_snapshot(used_tokens=2_000, session_id="s1")
        )
        snapshot = await read_context_usage(tmp_path, "s1")
        assert snapshot is not None
        assert snapshot.used_tokens == 2_000

    async def test_missing_store_returns_none(self, tmp_path: Path) -> None:
        """No store file for the bound session means None, never fabricated."""
        assert await read_context_usage(tmp_path, "s1") is None

    async def test_corrupted_store_returns_none(self, tmp_path: Path) -> None:
        """Garbage, wrong-shape, and wrong-type stores all read as None."""
        path = store_path(tmp_path, "bad")
        path.parent.mkdir(parents=True, exist_ok=True)
        for raw in (
            "not json at all{",
            "[1, 2, 3]",
            json.dumps({"session_id": 1, "used_tokens": "many"}),
        ):
            _ = path.write_text(raw, encoding="utf-8")
            assert await read_context_usage(tmp_path, "bad") is None

    async def test_stale_snapshot_returns_none(self, tmp_path: Path) -> None:
        """A TTL-stale snapshot for the bound session reads as None."""
        stale = make_snapshot(as_of=time.time() - 10_000, session_id="s1")
        await record_context_usage(tmp_path, stale)
        assert await read_context_usage(tmp_path, "s1") is None

    async def test_foreign_stale_file_does_not_block_bound_session(
        self, tmp_path: Path
    ) -> None:
        """A stale other-session file is irrelevant to the bound session."""
        await record_context_usage(
            tmp_path,
            make_snapshot(as_of=time.time() - 10_000, session_id="old"),
        )
        fresh = make_snapshot(used_tokens=3_000, session_id="new")
        await record_context_usage(tmp_path, fresh)
        assert await read_context_usage(tmp_path, "new") == fresh


class TestProducerScript:
    """Tests for scripts/cortex-context-usage-statusline.sh (tee behavior)."""

    def _run_script(self, project_root: Path, payload: bytes) -> bytes:
        """Run the producer with stdin payload; return stdout bytes."""
        env = dict(os.environ)
        env["CORTEX_CONTEXT_USAGE_PROJECT_DIR"] = str(project_root)
        result = subprocess.run(
            ["bash", str(PRODUCER_SCRIPT)],
            input=payload,
            capture_output=True,
            env=env,
            check=True,
            timeout=30,
        )
        return result.stdout

    def _hot_payload(self, session_id: str, total_input: int) -> bytes:
        """Build a synthetic in-context payload for one session."""
        return json.dumps(
            {
                "session_id": session_id,
                "context_window": {
                    "total_input_tokens": total_input,
                    "total_output_tokens": 5_000,
                    "context_window_size": 200_000,
                },
            }
        ).encode()

    @REQUIRES_JQ
    def test_host_fixture_passes_through_and_writes_session_store(
        self, tmp_path: Path
    ) -> None:
        """Fixture bytes exit unchanged; the session store gets one snapshot."""
        payload = HOST_FIXTURE.read_bytes()
        stdout = self._run_script(tmp_path, payload)
        assert stdout == payload
        store = json.loads(
            store_path(tmp_path, HOST_SESSION_ID).read_text(encoding="utf-8")
        )
        assert store["session_id"] == HOST_SESSION_ID
        assert store["used_tokens"] == 0
        assert store["limit_tokens"] == 200_000
        assert store["source"] == "statusline"
        assert store["as_of"] > 0

    @REQUIRES_JQ
    def test_payload_without_context_window_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        """Missing context_window leaves no store file; stdin still passes."""
        payload = b'{"session_id": "no-usage", "cwd": "/tmp"}'
        stdout = self._run_script(tmp_path, payload)
        assert stdout == payload
        assert session_files(tmp_path) == []

    @REQUIRES_JQ
    def test_payload_without_session_id_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        """Unattributable payloads never land on disk (fail closed)."""
        payload = json.dumps(
            {
                "context_window": {
                    "total_input_tokens": 5,
                    "total_output_tokens": 6,
                    "context_window_size": 200_000,
                }
            }
        ).encode()
        stdout = self._run_script(tmp_path, payload)
        assert stdout == payload
        assert session_files(tmp_path) == []

    @REQUIRES_JQ
    def test_same_session_latest_wins(self, tmp_path: Path) -> None:
        """Back-to-back runs for ONE session keep a single newest snapshot."""
        _ = self._run_script(tmp_path, self._hot_payload("s2", 100_000))
        _ = self._run_script(tmp_path, self._hot_payload("s2", 190_000))
        assert len(session_files(tmp_path)) == 1
        store = json.loads(store_path(tmp_path, "s2").read_text(encoding="utf-8"))
        assert store["session_id"] == "s2"
        assert store["used_tokens"] == 195_000
        assert store["used_percentage"] == pytest.approx(97.5)  # type: ignore[arg-type]

    @REQUIRES_JQ
    def test_two_sessions_write_distinct_files(self, tmp_path: Path) -> None:
        """Concurrent windows never overwrite each other's snapshot."""
        _ = self._run_script(tmp_path, HOST_FIXTURE.read_bytes())
        _ = self._run_script(tmp_path, self._hot_payload("s2", 190_000))
        assert {p.name for p in session_files(tmp_path)} == {
            f"context-usage-{HOST_SESSION_ID}.json",
            "context-usage-s2.json",
        }
        mine = asyncio.run(read_context_usage(tmp_path, "s2"))
        assert mine is not None
        assert mine.session_id == "s2"
        assert mine.used_tokens == 195_000
        # The other window's data stays invisible to a session bound to s2's id.
        assert asyncio.run(read_context_usage(tmp_path, HOST_SESSION_ID)) is not None
