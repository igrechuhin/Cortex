"""Small redacted failure summaries for the unchanged real stdio transport."""

# cspell:ignore pythonhosted

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

_CAPTURE_BYTES = 16384
_SUMMARY_CHARS = 1024
_ARTIFACT_CHARS = 8192
_URL = re.compile(r"\b(?:https?|ssh)://[^\s\"'<>]+", re.IGNORECASE)
_AUTH_HEADER = re.compile(
    r"\b((?:(?:proxy-)?authorization|(?:set-)?cookie)[\"']?\s*[:=]\s*)[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[^\s\"'<>]+", re.IGNORECASE)
_CREDENTIAL = re.compile(
    r"\b([\w-]*(?:token|secret|password|api[_-]?key|credential|authorization)"
    + r"[\w-]*\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
_ABSOLUTE_PATH = re.compile(r"(?<![\w>])/(?:[\w.@~+-]+/)+[\w.@~+-]*")
_TERMINAL_CONTROL = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\|$))"
)


class StdioFailureSummary(BaseModel):
    """Only bounded, redacted diagnostic text reaches pytest's failure summary."""

    version: int = 1
    error_type: str
    stderr_tail: str = Field(max_length=_SUMMARY_CHARS)
    truncated: bool
    diagnostic_artifact: Path | None = None


class EndpointKind(str, Enum):
    SIMPLE_INDEX = "simple-index"
    DISTRIBUTION = "distribution"
    OTHER = "other"


class SafeEndpoint(BaseModel):
    host: str = Field(max_length=253)
    kind: EndpointKind
    package: str | None = Field(default=None, max_length=128)

    def label(self) -> str:
        package = f" package={self.package}" if self.package else ""
        return f"<url host={self.host} endpoint={self.kind.value}{package}>"


class StdioDiagnosticArtifact(BaseModel):
    version: int = 1
    error_type: str = Field(max_length=128)
    stderr_tail: str = Field(max_length=_ARTIFACT_CHARS)
    truncated: bool
    endpoints: list[SafeEndpoint] = Field(max_length=16)


def _safe_endpoint(raw: str) -> SafeEndpoint | None:
    try:
        parsed = urlsplit(raw.rstrip("),.;`"))
        host = parsed.hostname
    except ValueError:
        return None
    if not host or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host):
        return None
    kind, package = EndpointKind.OTHER, None
    if host in {"pypi.org", "pypi.python.org"}:
        match = re.fullmatch(
            r"/simple/([a-z0-9][a-z0-9._-]{0,127})/?", parsed.path, re.IGNORECASE
        )
        if match:
            kind = EndpointKind.SIMPLE_INDEX
            package = re.sub(r"[-_.]+", "-", match.group(1)).lower()
    elif host == "files.pythonhosted.org":
        kind = EndpointKind.DISTRIBUTION
    return SafeEndpoint(host=host, kind=kind, package=package)


def _replace_url(match: re.Match[str], endpoints: list[SafeEndpoint]) -> str:
    endpoint = _safe_endpoint(match.group())
    if endpoint is None:
        return "<url redacted>"
    if endpoint in endpoints:
        endpoints.remove(endpoint)
    endpoints.append(endpoint)
    del endpoints[:-16]
    return endpoint.label()


def _bounded_tail(stream: TextIO) -> tuple[str, bool]:
    stream.flush()
    _ = stream.seek(0, os.SEEK_END)
    size = stream.tell()
    _ = stream.seek(max(0, size - _CAPTURE_BYTES))
    tail = stream.read(_CAPTURE_BYTES)
    if size > _CAPTURE_BYTES:
        # AI: A partial first line could begin inside an otherwise labeled secret.
        tail = tail.partition("\n")[2] or "<truncated single line>"
    return tail, size > _CAPTURE_BYTES


def _redact(
    text: str, root: Path, checkout: Path, endpoints: list[SafeEndpoint]
) -> str:
    # AI: Color and hyperlink controls must not interrupt secret labels or URLs.
    text = _TERMINAL_CONTROL.sub("", text)
    text = _AUTH_HEADER.sub(r"\1<redacted>", text)
    text = _URL.sub(lambda match: _replace_url(match, endpoints), text)
    text = _BEARER.sub("Bearer <redacted>", text)
    text = _CREDENTIAL.sub(r"\1<redacted>", text)
    paths = {
        str(checkout.resolve()): "<checkout>",
        str(root.resolve()): "<fixture>",
        str(Path.home()): "<home>",
    }
    for path, label in sorted(paths.items(), key=lambda item: -len(item[0])):
        text = text.replace(path, label)
    text = _ABSOLUTE_PATH.sub("<path>", text)
    return "\n".join(" ".join(line.split()) for line in text.splitlines())


def _diagnostic(
    stream: TextIO, error: Exception | None, root: Path, checkout: Path
) -> StdioDiagnosticArtifact:
    tail, truncated = _bounded_tail(stream)
    endpoints: list[SafeEndpoint] = []
    redacted = _redact(tail, root, checkout, endpoints) or "<no child stderr>"
    return StdioDiagnosticArtifact(
        error_type=type(error).__name__ if error else "completed",
        stderr_tail=redacted[-_ARTIFACT_CHARS:],
        truncated=truncated or len(redacted) > _ARTIFACT_CHARS,
        endpoints=endpoints,
    )


def _retain(artifact: StdioDiagnosticArtifact, path: Path | None) -> None:
    if path is not None:
        content = artifact.model_dump_json(indent=2) + "\n"
        assert len(content.encode("utf-8")) <= 65536
        with path.open("x", encoding="utf-8") as stream:
            _ = stream.write(content)


def _failure_message(artifact: StdioDiagnosticArtifact, path: Path | None) -> str:
    redacted = " ".join(artifact.stderr_tail.split())
    summary = StdioFailureSummary(
        error_type=artifact.error_type,
        stderr_tail=redacted[-_SUMMARY_CHARS:],
        truncated=artifact.truncated or len(redacted) > _SUMMARY_CHARS,
        diagnostic_artifact=path,
    )
    return "stdio startup diagnostics: " + summary.model_dump_json()


@contextmanager
def capture_stdio_failure(
    stream: TextIO, root: Path, checkout: Path, artifact_path: Path | None = None
) -> Iterator[None]:
    """Preserve the original traceback while retaining a short single-line cause."""
    try:
        yield
    except Exception as error:
        artifact = _diagnostic(stream, error, root, checkout)
        _retain(artifact, artifact_path)
        raise AssertionError(_failure_message(artifact, artifact_path)) from error
    else:
        _retain(_diagnostic(stream, None, root, checkout), artifact_path)
