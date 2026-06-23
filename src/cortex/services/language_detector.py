"""Language Detection Service

Detects project language(s), test frameworks, and build tools from project structure.
"""

import json
import logging
from pathlib import Path

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.path_resolver import get_venv_bin_path
from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)


class LanguageInfo(DictLikeModel):
    """Language detection result."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

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

        # Check for Swift
        if self._is_swift_project():
            return self._detect_swift_tooling()

        # Check for Kotlin
        if self._is_kotlin_project():
            return self._detect_kotlin_tooling()

        # Check for Java
        if self._is_java_project():
            return self._detect_java_tooling()

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

    def _is_swift_project(self) -> bool:
        """Check if project is Swift (SPM or Xcode)."""
        if (self.project_root / "Package.swift").exists():
            return True
        return any(self.project_root.glob("*.xcodeproj"))

    def _is_kotlin_project(self) -> bool:
        """Check if project is Kotlin (Gradle/Maven with Kotlin)."""
        root = self.project_root
        has_gradle = (root / "build.gradle").exists() or (
            root / "build.gradle.kts"
        ).exists()
        has_maven = (root / "pom.xml").exists()
        has_kt = any(root.rglob("*.kt"))
        return (has_gradle or has_maven) and has_kt

    def _is_java_project(self) -> bool:
        """Check if project is Java (Maven or Gradle, non-Kotlin)."""
        root = self.project_root
        has_build = (
            (root / "pom.xml").exists()
            or (root / "build.gradle").exists()
            or (root / "build.gradle.kts").exists()
        )
        if not has_build:
            return False
        # If Kotlin sources exist, prefer Kotlin detection.
        return not any(root.rglob("*.kt"))

    def _package_json_has_typescript(self) -> bool:
        """Check if package.json indicates TypeScript."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return False
        try:
            with package_json.open() as f:
                data = json.load(f)
                return (
                    "typescript" in str(data.get("dependencies", {}))
                    or "typescript" in str(data.get("devDependencies", {}))
                    or (self.project_root / "tsconfig.json").exists()
                )
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.debug("_detect_typescript: %s", e)
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

    def _detect_swift_tooling(self) -> LanguageInfo:
        """Detect Swift tooling (SPM or Xcode)."""
        is_xcode = not (self.project_root / "Package.swift").exists() and any(
            self.project_root.glob("*.xcodeproj")
        )
        return LanguageInfo(
            language="swift",
            test_framework="xcodebuild test" if is_xcode else "swift test",
            formatter="swift format" if not is_xcode else None,
            linter=None,
            type_checker="xcodebuild" if is_xcode else "swift build",
            build_tool="xcodebuild" if is_xcode else "swift",
            confidence=0.9,
        )

    def _detect_kotlin_tooling(self) -> LanguageInfo:
        """Detect Kotlin tooling (Gradle/Maven)."""
        return LanguageInfo(
            language="kotlin",
            test_framework=None,
            formatter="spotless",
            linter=None,
            type_checker=None,
            build_tool="gradle",
            confidence=0.85,
        )

    def _detect_java_tooling(self) -> LanguageInfo:
        """Detect Java tooling (Maven or Gradle)."""
        root = self.project_root
        build_tool = None
        if (root / "pom.xml").exists():
            build_tool = "maven"
        elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            build_tool = "gradle"
        return LanguageInfo(
            language="java",
            test_framework=None,
            formatter="spotless",
            linter=None,
            type_checker=None,
            build_tool=build_tool,
            confidence=0.8,
        )

    def _detect_js_test_framework(self) -> str | None:
        """Detect JavaScript/TypeScript test framework."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return None
        try:
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
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.debug("_detect_js_test_framework: %s", e)
        return None

    def _has_python_tool(self, tool: str) -> bool:
        """Check if Python tool is available."""
        venv_bin = get_venv_bin_path(self.project_root) / tool
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
