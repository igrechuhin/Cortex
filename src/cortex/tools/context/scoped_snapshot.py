"""Request-local selected input snapshot; the resource TTL cache remains the owner."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.session_goal_models import SessionGoal
from cortex.tools.context.scoped_source_state import ScopedSourceState
from cortex.tools.context.scoped_task_state import ScopedTaskState
from cortex.tools.context.source_revision import SourceRevision


class ScopedSnapshot(BaseModel):
    """Retain bytes once for derivation, then recheck only selected file revisions."""

    model_config = ConfigDict(extra=EXTRA_FORBID, arbitrary_types_allowed=True)

    root: Path
    scope: str
    sources: dict[str, SourceRevision] = Field(
        default_factory=dict[str, SourceRevision]
    )
    texts: dict[str, str] = Field(default_factory=dict[str, str])
    paths: dict[str, Path] = Field(default_factory=dict[str, Path])
    memberships: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    plans: dict[str, str] = Field(default_factory=dict[str, str])
    upstream: list[str] = Field(default_factory=list[str])
    summaries: dict[str, str | None] = Field(default_factory=dict[str, str | None])
    rules: str = ""
    goal: SessionGoal | None = None
    task: ScopedTaskState = Field(default_factory=ScopedTaskState)

    def issue(self, code: str, sources: list[str], message: str) -> None:
        self.task.issue(code, sources, message)

    def add_text(self, identity: str, text: str, kind: str, reference: str) -> None:
        self.texts[identity] = text
        self.sources[identity] = SourceRevision(
            identity=identity,
            kind=kind,
            reference=reference,
            provenance="selected rendered input (UTF-8)",
            revision=sha256(text.encode("utf-8")).hexdigest(),
        )

    def read(
        self, path: Path, kind: str = "context", identity: str | None = None
    ) -> str:
        reference = path.resolve().as_posix()
        if path.is_relative_to(self.root):
            reference = path.relative_to(self.root).as_posix()
        key = identity or f"file:{reference}"
        if key in self.texts:
            return self.texts[key]
        self.paths[key] = path
        try:
            raw = path.read_bytes()
            # AI: Hash the same bytes used for decoding; newline translation would falsify provenance.
        except OSError as exc:
            state = (
                ScopedSourceState.MISSING
                if isinstance(exc, FileNotFoundError)
                else ScopedSourceState.UNREADABLE
            )
            self.sources[key] = SourceRevision(
                identity=key,
                kind=kind,
                reference=reference,
                provenance="selected canonical file",
                state=state,
            )
            raise
        return self._decode_bytes(key, kind, reference, raw)

    def _decode_bytes(self, key: str, kind: str, reference: str, raw: bytes) -> str:
        source = SourceRevision(
            identity=key,
            kind=kind,
            reference=reference,
            provenance="selected canonical file (exact bytes)",
            revision=sha256(raw).hexdigest(),
        )
        self.sources[key] = source
        try:
            self.texts[key] = raw.decode("utf-8")
        except UnicodeError:
            self.sources[key] = source.model_copy(
                update={"state": ScopedSourceState.INVALID}
            )
            raise
        return self.texts[key]

    def fingerprint(self) -> str:
        manifest = "\n".join(
            self.sources[key].model_dump_json() for key in sorted(self.sources)
        )
        return sha256(manifest.encode("utf-8")).hexdigest()

    def files_unchanged(self) -> bool:
        for key, path in self.paths.items():
            try:
                revision = sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                state = (
                    ScopedSourceState.MISSING
                    if isinstance(exc, FileNotFoundError)
                    else ScopedSourceState.UNREADABLE
                )
                if self.sources[key].state != state:
                    return False
                continue
            if revision != self.sources[key].revision:
                return False
        return True
