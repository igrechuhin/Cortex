"""Language Detection Service

Detects project language(s), test frameworks, and build tools from project structure.
"""

from pathlib import Path

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel


class LanguageInfo(DictLikeModel):
    """Language detection result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    language: str = Field(description="Detected programming language")
    test_framework: str | None = Field(
        default=None, description="Test framework if detected"
    )
    formatter: str | None = Field(
        default=None, description="Code formatter if detected"
    )
    linter: str | None = Field(default=None, description="Linter if detected")
    type_checker: str | None = Field(
        default=None, description="Type checker if detected"
    )
    build_tool: str | None = Field(default=None, description="Build tool if detected")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence (0-1)")


class LanguageDetector:
    """Detects project language and tooling from project structure."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize detector with project root.

        Args:
            project_root: Path to project root directory. If None, uses
            current directory.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def detect_language(self) -> LanguageInfo | None:
        """Detect project language and tooling.

        Returns:
            LanguageInfo if language detected, None otherwise.
        """
        # Check for Python
        if self._is_python_project():
            return self._detect_python_tooling()

        # Check for TypeScript
        if self._is_typescript_project():
            return self._detect_typescript_tooling()

        # Check for JavaScript
        if self._is_javascript_project():
            return self._detect_javascript_tooling()

        # Check for Rust
        if self._is_rust_project():
            return self._detect_rust_tooling()

        # Check for Go
        if self._is_go_project():
            return self._detect_go_tooling()

        return None

    def _is_python_project(self) -> bool:
        """Check if project is Python."""
        return (
            (self.project_root / "pyproject.toml").exists()
            or (self.project_root / "setup.py").exists()
            or (self.project_root / "requirements.txt").exists()
            or (self.project_root / "Pipfile").exists()
            or any(
                (self.project_root / f).exists()
                for f in ["setup.cfg", "tox.ini", "pytest.ini"]
            )
        )

    def _is_typescript_project(self) -> bool:
        """Check if project is TypeScript."""
        return (
            (self.project_root / "tsconfig.json").exists()
            or (self.project_root / "package.json").exists()
            and self._package_json_has_typescript()
        )

    def _is_javascript_project(self) -> bool:
        """Check if project is JavaScript."""
        return (
            self.project_root / "package.json"
        ).exists() and not self._package_json_has_typescript()

    def _is_rust_project(self) -> bool:
        """Check if project is Rust."""
        return (self.project_root / "Cargo.toml").exists()

    def _is_go_project(self) -> bool:
        """Check if project is Go."""
        return (self.project_root / "go.mod").exists() or (
            self.project_root / "go.sum"
        ).exists()

    def _package_json_has_typescript(self) -> bool:
        """Check if package.json indicates TypeScript."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return False
        try:
            import json

            with package_json.open() as f:
                data = json.load(f)
                return (
                    "typescript" in str(data.get("dependencies", {}))
                    or "typescript" in str(data.get("devDependencies", {}))
                    or (self.project_root / "tsconfig.json").exists()
                )
        except Exception:
            return False

    def _detect_python_tooling(self) -> LanguageInfo:
        """Detect Python tooling."""
        test_framework = (
            "pytest" if (self.project_root / "pytest.ini").exists() else None
        )
        formatter = "black" if self._has_python_tool("black") else None
        linter = "ruff" if self._has_python_tool("ruff") else None
        type_checker = "pyright" if self._has_python_tool("pyright") else None

        return LanguageInfo(
            language="python",
            test_framework=test_framework,
            formatter=formatter,
            linter=linter,
            type_checker=type_checker,
            build_tool=None,
            confidence=0.9,
        )

    def _detect_typescript_tooling(self) -> LanguageInfo:
        """Detect TypeScript tooling."""
        test_framework = self._detect_js_test_framework()
        formatter = "prettier" if self._has_js_tool("prettier") else None
        linter = "eslint" if self._has_js_tool("eslint") else None
        type_checker = "tsc" if (self.project_root / "tsconfig.json").exists() else None

        return LanguageInfo(
            language="typescript",
            test_framework=test_framework,
            formatter=formatter,
            linter=linter,
            type_checker=type_checker,
            build_tool=None,
            confidence=0.85,
        )

    def _detect_javascript_tooling(self) -> LanguageInfo:
        """Detect JavaScript tooling."""
        test_framework = self._detect_js_test_framework()
        formatter = "prettier" if self._has_js_tool("prettier") else None
        linter = "eslint" if self._has_js_tool("eslint") else None

        return LanguageInfo(
            language="javascript",
            test_framework=test_framework,
            formatter=formatter,
            linter=linter,
            type_checker=None,
            build_tool=None,
            confidence=0.8,
        )

    def _detect_rust_tooling(self) -> LanguageInfo:
        """Detect Rust tooling."""
        return LanguageInfo(
            language="rust",
            test_framework="cargo test",
            formatter="rustfmt",
            linter="clippy",
            type_checker=None,
            build_tool="cargo",
            confidence=0.95,
        )

    def _detect_go_tooling(self) -> LanguageInfo:
        """Detect Go tooling."""
        return LanguageInfo(
            language="go",
            test_framework="go test",
            formatter="gofmt",
            linter="golangci-lint",
            type_checker=None,
            build_tool="go",
            confidence=0.9,
        )

    def _detect_js_test_framework(self) -> str | None:
        """Detect JavaScript/TypeScript test framework."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return None
        try:
            import json

            with package_json.open() as f:
                data = json.load(f)
                deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }
                if "jest" in deps:
                    return "jest"
                if "vitest" in deps:
                    return "vitest"
                if "mocha" in deps:
                    return "mocha"
        except Exception:
            pass
        return None

    def _has_python_tool(self, tool: str) -> bool:
        """Check if Python tool is available."""
        venv_bin = self.project_root / ".venv" / "bin" / tool
        if venv_bin.exists():
            return True
        # Check if tool is in PATH
        import shutil

        return shutil.which(tool) is not None

    def _has_js_tool(self, tool: str) -> bool:
        """Check if JavaScript tool is available."""
        node_modules = self.project_root / "node_modules" / ".bin" / tool
        if node_modules.exists():
            return True
        # Check if tool is in PATH
        import shutil

        return shutil.which(tool) is not None
