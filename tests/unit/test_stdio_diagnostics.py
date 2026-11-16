"""Bounded startup evidence retains causes without exposing child secrets."""

# cspell:ignore sdists pythonhosted

import base64
import io
from pathlib import Path

import pytest

from tests.helpers.stdio_diagnostics import (
    EndpointKind,
    StdioDiagnosticArtifact,
    StdioFailureSummary,
    capture_stdio_failure,
)
from tests.helpers.uv_test_state import UvTestState, owned_uv_state, require_uv_state
from tests.integration.test_artifact_migration_protocol import server_parameters


def _capture(stderr: str, root: Path, checkout: Path) -> tuple[str, BaseException]:
    original = RuntimeError("Connection closed")
    with pytest.raises(AssertionError) as caught:
        with capture_stdio_failure(io.StringIO(stderr), root, checkout):
            raise original
    assert caught.value.__cause__ is original
    assert original.__traceback__ is not None
    return str(caught.value), original


def _summary(message: str) -> StdioFailureSummary:
    prefix = "stdio startup diagnostics: "
    assert message.startswith(prefix)
    return StdioFailureSummary.model_validate_json(message.removeprefix(prefix))


def test_startup_summary_redacts_credentials_and_private_paths(tmp_path: Path) -> None:
    root, checkout = tmp_path / "fixture", tmp_path / "checkout"
    stderr = (
        f"{checkout}/src/cortex/main.py\n{root}/work.md\n"
        f"{Path.home()}/private/error.log\n/opt/private/hidden.log\n"
        "https://user:credential@example.test/path?token=url-secret\n"
        "API_KEY=assignment-secret password='quoted secret'\n"
        "Authorization: Bearer bearer-secret\n"
    )
    message, _ = _capture(stderr, root, checkout)
    assert "\n" not in message and "\r" not in message
    for secret in ("assignment-secret", "quoted secret", "bearer-secret", "url-secret"):
        assert secret not in message
    for path in (str(tmp_path), str(Path.home()), "/opt/private"):
        assert path not in message
    assert "<checkout>/src/cortex/main.py" in message
    assert "<fixture>/work.md" in message


def test_startup_summary_bounds_read_and_retains_final_error(tmp_path: Path) -> None:
    stderr = "noise" * 20000 + "\nerror: invalid startup option\n"
    message, _ = _capture(stderr, tmp_path, tmp_path / "checkout")
    summary = _summary(message)
    assert summary.truncated is True
    assert len(message) < 1400
    assert "invalid startup option" in message


def test_terminal_controls_cannot_hide_credentials_or_urls(tmp_path: Path) -> None:
    stderr = (
        "Authorization:\x1b[31m Bearer colored-bearer\x1b[0m\n"
        "API_\x1b[32mKEY=colored-key\x1b[0m\n"
        "https\x1b[33m://user:colored-url@example.test/?token=colored-query\x1b[0m\n"
        "\x1b]8;;https://user:osc-secret@example.test/\x07label\x1b]8;;\x1b\\\n"
    )
    message, _ = _capture(stderr, tmp_path, tmp_path / "checkout")
    for secret in (
        "colored-bearer",
        "colored-key",
        "colored-url",
        "colored-query",
        "osc-secret",
    ):
        assert secret not in message
    assert "\\u001b" not in message


def test_truncated_unlabeled_single_line_is_not_disclosed(tmp_path: Path) -> None:
    message, _ = _capture("sensitive" * 10000, tmp_path, tmp_path / "checkout")
    assert "sensitive" not in message
    assert "<truncated single line>" in message
    assert _summary(message).truncated is True


def test_empty_stderr_is_explicit_without_replacing_original_cause(
    tmp_path: Path,
) -> None:
    message, original = _capture("", tmp_path, tmp_path / "checkout")
    summary = _summary(message)
    assert summary.error_type == type(original).__name__
    assert summary.stderr_tail == "<no child stderr>"
    assert summary.truncated is False


def test_denial_reason_retains_only_home_relative_target(tmp_path: Path) -> None:
    stderr = f"failed to open {Path.home()}/.cache/uv/sdists-v9/.git: Permission denied (os error 13)\n"
    message, _ = _capture(stderr, tmp_path, tmp_path / "checkout")
    assert str(Path.home()) not in message
    assert "<home>/.cache/uv/sdists-v9/.git" in message
    assert "Permission denied (os error 13)" in message


def test_packaged_parameters_preserve_real_refresh_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYTHONPATH", "untrusted-source-overlay")
    monkeypatch.setenv("UV_NO_SYNC", "1")
    inherited = str(tmp_path / "inherited-cache")
    monkeypatch.setenv("UV_CACHE_DIR", inherited)
    with owned_uv_state(tmp_path) as state:
        parameters = server_parameters(tmp_path, "packaged", state)
        assert parameters.env is not None
        assert parameters.env["UV_CACHE_DIR"] == str(state.cache)
        assert parameters.env["UV_TOOL_DIR"] == str(state.tools)
        assert parameters.env["UV_CACHE_DIR"] != inherited
    assert not state.base.exists()
    checkout = Path(__file__).resolve().parents[2]
    assert parameters.command == "uvx"
    assert parameters.args == [
        "--verbose",
        "--refresh-package",
        "cortex",
        "--from",
        str(checkout),
        "cortex",
    ]
    assert parameters.cwd == tmp_path
    assert parameters.env is not None
    assert parameters.env["PYTHONPATH"] == ""
    assert parameters.env["UV_NO_SYNC"] == "1"


def test_packaged_parameters_require_explicit_cache_before_launch(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="explicit owned uv state"):
        _ = server_parameters(tmp_path, "packaged")
    invalid = UvTestState(
        base=tmp_path,
        cache=tmp_path / "cache",
        tools=tmp_path / "tools",
        home=tmp_path / "home",
    )
    with pytest.raises(ValueError, match="outside the project"):
        _ = require_uv_state(tmp_path, invalid)


def test_cache_is_unique_outside_project_and_lives_until_context_exit(
    tmp_path: Path,
) -> None:
    with owned_uv_state(tmp_path) as first:
        with owned_uv_state(tmp_path) as second:
            assert first.base != second.base
            assert first.cache.is_dir() and second.tools.is_dir()
            assert first.base.parent == second.base.parent == tmp_path.resolve().parent
            assert not first.base.is_relative_to(tmp_path.resolve())
        assert first.base.is_dir() and not second.base.exists()
    assert not first.base.exists()


def test_cache_uses_physical_project_parent_for_symlink_root(tmp_path: Path) -> None:
    physical = tmp_path / "physical" / "project"
    physical.mkdir(parents=True)
    alias = tmp_path / "alias"
    alias.symlink_to(physical, target_is_directory=True)
    with owned_uv_state(alias) as state:
        assert state.base == state.base.resolve(strict=True)
        assert state.base.parent == physical.parent.resolve()
        assert not state.cache.is_relative_to(physical.resolve())


def test_cache_is_cleaned_after_exception_without_mutating_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inherited = str(tmp_path / "unchanged-cache")
    monkeypatch.setenv("UV_CACHE_DIR", inherited)
    state: UvTestState | None = None
    with pytest.raises(RuntimeError, match="synthetic protocol failure"):
        with owned_uv_state(tmp_path) as state:
            assert state.cache.exists() and state.tools.exists()
            raise RuntimeError("synthetic protocol failure")
    assert state is not None and not state.base.exists()
    environment = server_parameters(tmp_path, "editable").env
    assert environment is not None
    assert environment["UV_CACHE_DIR"] == inherited


def test_owned_environment_does_not_inherit_home_credentials_or_python_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "UV_TOOL_DIR",
        "UV_CONFIG_FILE",
        "UV_PYTHON",
        "NETRC",
        "PYTHONPATH",
        "UV_INDEX_TOKEN",
    ):
        monkeypatch.setenv(name, "untrusted-home-state")
    with owned_uv_state(tmp_path) as state:
        environment = state.environment()
        assert environment["HOME"] == str(state.home)
        assert environment["UV_TOOL_DIR"] == str(state.tools)
        assert environment["UV_NO_CONFIG"] == "1"
        assert environment["UV_PYTHON_DOWNLOADS"] == "never"
        assert environment["UV_KEYRING_PROVIDER"] == "disabled"
        assert (
            "UV_CONFIG_FILE" not in environment and "UV_INDEX_TOKEN" not in environment
        )
        assert Path(environment["UV_PYTHON"]).is_absolute()
        assert Path(environment["NETRC"]).read_text() == ""
        assert environment["PYTHONPATH"] == ""


def _retained_capture(stderr: str, root: Path) -> StdioDiagnosticArtifact:
    path = root / "sanitized-diagnostic.json"
    original = RuntimeError("Connection closed")
    with pytest.raises(AssertionError) as caught:
        with capture_stdio_failure(io.StringIO(stderr), root, root / "checkout", path):
            raise original
    assert caught.value.__cause__ is original
    assert _summary(str(caught.value)).diagnostic_artifact == path
    assert path.stat().st_size <= 65536
    return StdioDiagnosticArtifact.model_validate_json(path.read_text())


@pytest.mark.parametrize(
    "header", ["Authorization", "Proxy-Authorization", "Cookie", "Set-Cookie"]
)
def test_retained_headers_remove_entire_values(tmp_path: Path, header: str) -> None:
    encoded = base64.b64encode(b"test-user:test-password").decode("ascii")
    raw = f"{header}:\x1b[31m Basic {encoded}\x1b[0m; session=hidden-cookie\nerror: safe\n"
    artifact = _retained_capture(raw, tmp_path)
    assert encoded not in artifact.stderr_tail
    assert "hidden-cookie" not in artifact.stderr_tail
    assert "error: safe" in artifact.stderr_tail


def test_retained_folded_authorization_has_no_credential_suffix(tmp_path: Path) -> None:
    artifact = _retained_capture(
        "Authorization: Basic\n hidden-folded-value\nerror: safe\n", tmp_path
    )
    assert "hidden-folded-value" not in artifact.stderr_tail


@pytest.mark.parametrize(
    "url,host,kind,package",
    [
        (
            "https://private-user:private-password@pypi.org/simple/FastMCP/?token=hidden-query#hidden-fragment",
            "pypi.org",
            EndpointKind.SIMPLE_INDEX,
            "fastmcp",
        ),
        (
            "https://files.pythonhosted.org/packages/private-path?token=hidden-query",
            "files.pythonhosted.org",
            EndpointKind.DISTRIBUTION,
            None,
        ),
        (
            "https://example.test/private-path?token=hidden-query",
            "example.test",
            EndpointKind.OTHER,
            None,
        ),
    ],
)
def test_safe_endpoint_metadata_discards_credentials_and_arbitrary_path(
    tmp_path: Path, url: str, host: str, kind: EndpointKind, package: str | None
) -> None:
    artifact = _retained_capture("fetch " + url + "\n", tmp_path)
    assert len(artifact.endpoints) == 1
    endpoint = artifact.endpoints[0]
    assert (endpoint.host, endpoint.kind, endpoint.package) == (host, kind, package)
    for secret in (
        "private-user",
        "private-password",
        "private-path",
        "hidden-query",
        "hidden-fragment",
    ):
        assert secret not in artifact.model_dump_json()


def test_invalid_url_never_falls_back_to_raw_value(tmp_path: Path) -> None:
    artifact = _retained_capture(
        "fetch https://private-user:private-password@[invalid\n", tmp_path
    )
    assert artifact.endpoints == []
    assert "private-user" not in artifact.stderr_tail
    assert "private-password" not in artifact.stderr_tail


def test_retained_partial_tail_and_endpoint_list_stay_bounded(tmp_path: Path) -> None:
    raw = "Authorization: Basic " + "X" * 25000 + "\n"
    raw += "\n".join(
        f"fetch https://node-{number}.example.test/private?token=hidden-query"
        for number in range(100)
    )
    artifact = _retained_capture(raw, tmp_path)
    assert artifact.truncated is True
    assert len(artifact.stderr_tail) <= 8192 and len(artifact.endpoints) <= 16
    assert (
        "X" * 32 not in artifact.stderr_tail
        and "hidden-query" not in artifact.stderr_tail
    )


def test_success_also_retains_only_sanitized_stderr(tmp_path: Path) -> None:
    path = tmp_path / "safe-success.json"
    with capture_stdio_failure(
        io.StringIO("fetch https://pypi.org/simple/uv-build/?token=hidden-query\n"),
        tmp_path,
        tmp_path / "checkout",
        path,
    ):
        pass
    artifact = StdioDiagnosticArtifact.model_validate_json(path.read_text())
    assert artifact.error_type == "completed"
    assert artifact.endpoints[0].package == "uv-build"
    assert "hidden-query" not in path.read_text()
