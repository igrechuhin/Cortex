# Step 2 of 8 — Create file_language_router.py

**Series**: Per-File Language Quality Gate
**Date Created**: 26-03-29
**Status**: Ready for Implementation
**Depends on**: `swift-qg-s1-add-extension-script-map.plan.md` (EXTENSION_SCRIPT_MAP must exist)
**Next step**: `swift-qg-s3-update-pipeline-quality.plan.md`

---

## Goal

Create `src/cortex/tools/execution/file_language_router.py` — the dispatcher that:

1. Groups project files by extension using `EXTENSION_SCRIPT_MAP`.
2. Invokes the correct synapse scripts for each language group via `FILES` env var.
3. Parses structured violations from script output.
4. Returns merged `(list[FileSizeViolation], list[FunctionLengthViolation])`.

---

## Files to Read First

1. `src/cortex/core/constants.py` — to import `EXTENSION_SCRIPT_MAP`, `FILE_SIZE_EXCLUDED_FILENAMES`, `MAX_FILE_LINES`, `MAX_FUNCTION_LINES`
2. `src/cortex/tools/execution/pre_commit_synapse.py` — to understand `_execute_synapse_script_subprocess`, `_resolve_synapse_python_bin`, `_synapse_script_skipped_result`
3. `src/cortex/tools/execution/pre_commit_helpers_models.py` — for `FileSizeViolation`, `FunctionLengthViolation`, `CheckResult` types
4. `src/cortex/core/path_resolver.py` — to import `get_cortex_path`, `CortexResourceType`
5. `.cortex/synapse/scripts/swift/check_file_sizes.py` — to confirm exact stderr output format
6. `.cortex/synapse/scripts/swift/check_function_lengths.py` — to confirm exact stderr output format
7. `.cortex/synapse/scripts/python/check_file_sizes.py` — to confirm exact stderr output format
8. `.cortex/synapse/scripts/python/check_function_lengths.py` — to confirm exact stderr output format

---

## File to Create

`src/cortex/tools/execution/file_language_router.py`

**Hard constraints**: ≤ 400 lines total; every function ≤ 30 logical lines.

---

## Public API (exact signatures)

```python
def route_files(
    files: list[Path],
    extension_map: dict[str, str] | None = None,
) -> dict[str, list[Path]]:
    """Group files by their language directory.

    Returns mapping of language dir → file list.
    Files with unknown extensions are silently omitted.
    extension_map overrides EXTENSION_SCRIPT_MAP (for testing).
    """

def collect_project_files(project_root: Path) -> list[Path]:
    """Return all checkable source files under project_root.

    Skips: __pycache__, .git, node_modules, .venv, build, dist directories.
    Does NOT skip test directories or test_* files — that is the scripts' job
    in fallback mode; when FILES is set, scripts check exactly what is given.
    Skips FILE_SIZE_EXCLUDED_FILENAMES (e.g. models.py) by name.
    Returns sorted list of absolute Paths.
    """

def run_quality_checks_for_all_languages(
    project_root: Path,
    files: list[Path] | None = None,
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]:
    """Dispatch quality checks to per-language synapse scripts.

    If files is None, calls collect_project_files(project_root).
    Returns (file_size_violations, function_length_violations) merged across all languages.
    Returns ([], []) when no files match known extensions — not an error.
    """
```

---

## Private Helpers (all prefixed `_`)

```python
def _files_env_value(files: list[Path]) -> str:
    """Return newline-separated absolute paths string for FILES env var."""

def _run_script_with_files(
    project_root: Path,
    language: str,
    script_name: str,
    files: list[Path],
) -> CheckResult:
    """Run a synapse script passing FILES env var.

    Resolves script path via get_cortex_path(project_root, CortexResourceType.SYNAPSE).
    Returns skipped CheckResult if script does not exist.
    Merges FILES into os.environ: env={**os.environ, "FILES": _files_env_value(files)}.
    """

def _parse_file_size_violations(
    output: str,
    project_root: Path,
) -> list[FileSizeViolation]:
    """Parse check_file_sizes.py stderr into FileSizeViolation objects.

    Handles both Python and Swift output formats (same line format):
      "  path/to/file.ext: 450 lines (max: 400, excess: 50)"
    Silently skips unrecognised lines (forward-compatible).
    """

def _parse_function_length_violations(
    output: str,
    project_root: Path,
    language: str,
) -> list[FunctionLengthViolation]:
    """Parse check_function_lengths.py stderr into FunctionLengthViolation objects.

    Python format (two-line: file header, then function):
      "  src/cortex/foo.py:"
      "    my_func() at line 42: 35 lines (max: 30, excess: 5)"

    Swift format (one-line):
      "  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)"

    Silently skips unrecognised lines.
    """
```

---

## Script Output Formats (exact — use these for regex patterns)

**Both `check_file_sizes.py` variants write to stderr:**

```text
❌ File size violations detected:

  <relative-path>: <N> lines (max: <M>, excess: <E>)

Total violations: ...
```

Regex for violation line: `r"^\s+(\S.+?):\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"`

**Python `check_function_lengths.py` stderr (two-line format):**

```text
  src/cortex/foo.py:
    my_func() at line 42: 35 lines (max: 30, excess: 5)
```

File header regex: `r"^\s+(\S.+\.py):$"`
Function line regex: `r"^\s+(\w+)\(\) at line (\d+):\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"`

**Swift `check_function_lengths.py` stderr (one-line format):**

```text
  Sources/Foo/Bar.swift:42: myFunc() — 35 lines (max: 30, excess: 5)
```

Regex: `r"^\s+(\S.+\.swift):(\d+):\s+(\w+)\(\)\s+—\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"`

---

## Correctness Notes

- `_run_script_with_files` merges FILES into the inherited environment:
  `env={**os.environ, "FILES": _files_env_value(files)}` — so scripts inherit
  `PATH`, `VIRTUAL_ENV`, etc.
- `collect_project_files` must include files under `Tests/` — the TradeWing bug was
  that test files were excluded. Do NOT filter by `test_*` prefix here.
- `_parse_*` functions must never raise — wrap in try/except and skip bad lines.
- `SKIP_DIRS` constant (used in `collect_project_files`): `{"__pycache__", ".git",
  "node_modules", ".venv", "venv", "build", "dist", ".tox", ".mypy_cache"}`.
- Use `os.environ` (not `{}`) as the base for the subprocess env.

---

## Skeleton (implementation guide)

```python
"""Per-extension quality check dispatcher."""

import os
import re
import subprocess
from pathlib import Path

from cortex.core.constants import (
    EXTENSION_SCRIPT_MAP,
    FILE_SIZE_EXCLUDED_FILENAMES,
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
)
from cortex.core.path_resolver import CortexResourceType, get_cortex_path, get_venv_bin_path
from cortex.services.framework_adapters.base import CheckResult
from cortex.tools.execution.pre_commit_helpers_models import (
    FileSizeViolation,
    FunctionLengthViolation,
)

_SKIP_DIRS: frozenset[str] = frozenset({
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "build", "dist", ".tox", ".mypy_cache",
})

_FILE_SIZE_VIOLATION_RE = re.compile(
    r"^\s+(\S.+?):\s+(\d+) lines \(max:\s*(\d+),\s*excess:\s*(\d+)\)"
)
# ... other patterns ...


def route_files(
    files: list[Path],
    extension_map: dict[str, str] | None = None,
) -> dict[str, list[Path]]: ...

def collect_project_files(project_root: Path) -> list[Path]: ...

def run_quality_checks_for_all_languages(
    project_root: Path,
    files: list[Path] | None = None,
) -> tuple[list[FileSizeViolation], list[FunctionLengthViolation]]: ...

def _files_env_value(files: list[Path]) -> str: ...

def _run_script_with_files(
    project_root: Path, language: str, script_name: str, files: list[Path]
) -> CheckResult: ...

def _parse_file_size_violations(output: str, project_root: Path) -> list[FileSizeViolation]: ...

def _parse_function_length_violations(
    output: str, project_root: Path, language: str
) -> list[FunctionLengthViolation]: ...
```

---

## Success Criteria

- [ ] File exists at `src/cortex/tools/execution/file_language_router.py`
- [ ] All three public functions are implemented with correct type signatures
- [ ] `route_files([Path("a.py"), Path("b.swift")])` returns `{"python": [...], "swift": [...]}`
- [ ] `collect_project_files` includes `Tests/` subdirectory files
- [ ] `collect_project_files` excludes `__pycache__`, `.git`
- [ ] `_parse_file_size_violations` parses both Python and Swift output formats
- [ ] `_parse_function_length_violations` parses both Python and Swift output formats
- [ ] File is ≤ 400 lines; all functions ≤ 30 logical lines
- [ ] No `Any` type; 100% type hints
- [ ] `run_quality_gate()` passes (this file is not yet wired in — no behaviour change yet)
