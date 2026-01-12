"""
Infrastructure Validator

Validates project infrastructure consistency, including:
- CI workflow vs commit prompt alignment
- Code quality standards consistency
- Documentation consistency
- Configuration consistency
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

try:
    import yaml  # type: ignore[reportMissingModuleSource]
except ImportError:
    yaml = None  # type: ignore[assignment,unused-ignore]


class InfrastructureIssue(TypedDict):
    """Infrastructure validation issue."""

    type: str
    severity: str
    description: str
    location: str
    suggestion: str
    ci_check: str | None
    missing_in_commit: bool


class InfrastructureValidationResult(TypedDict):
    """Infrastructure validation result."""

    status: str
    check_type: str
    checks_performed: dict[str, bool]
    issues_found: list[InfrastructureIssue]
    recommendations: list[str]


class InfrastructureValidator:
    """Validates project infrastructure consistency."""

    def __init__(self, project_root: Path) -> None:
        """Initialize infrastructure validator.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = project_root
        self.ci_workflow_path = project_root / ".github" / "workflows" / "quality.yml"
        self.commit_prompt_path = (
            project_root / ".cortex" / "synapse" / "prompts" / "commit.md"
        )

    async def validate_infrastructure(
        self,
        check_commit_ci_alignment: bool = True,
        check_code_quality_consistency: bool = True,
        check_documentation_consistency: bool = True,
        check_config_consistency: bool = True,
    ) -> InfrastructureValidationResult:
        """Validate project infrastructure consistency.

        Args:
            check_commit_ci_alignment: Check commit prompt vs CI workflow alignment
            check_code_quality_consistency: Check code quality standards consistency
            check_documentation_consistency: Check documentation consistency
            check_config_consistency: Check configuration consistency

        Returns:
            Infrastructure validation result
        """
        issues: list[InfrastructureIssue] = []
        recommendations: list[str] = []
        checks_performed: dict[str, bool] = {}

        checks_to_run = self._get_checks_to_run(
            check_commit_ci_alignment,
            check_code_quality_consistency,
            check_documentation_consistency,
            check_config_consistency,
        )

        for check_name, check_func in checks_to_run:
            await self._run_check(
                check_name, check_func, issues, recommendations, checks_performed
            )

        return {
            "status": "success",
            "check_type": "infrastructure",
            "checks_performed": checks_performed,
            "issues_found": issues,
            "recommendations": recommendations,
        }

    def _get_checks_to_run(
        self,
        check_commit_ci_alignment: bool,
        check_code_quality_consistency: bool,
        check_documentation_consistency: bool,
        check_config_consistency: bool,
    ) -> list[tuple[str, Callable[[], tuple[list[InfrastructureIssue], list[str]]]]]:
        """Get list of checks to run based on flags.

        Args:
            check_commit_ci_alignment: Whether to check commit/CI alignment
            check_code_quality_consistency: Whether to check code quality consistency
            check_documentation_consistency: Whether to check documentation consistency
            check_config_consistency: Whether to check config consistency

        Returns:
            List of (check_name, check_function) tuples
        """
        checks: list[tuple[str, Callable[[], tuple[list[InfrastructureIssue], list[str]]]]] = []
        if check_commit_ci_alignment:
            checks.append(("commit_ci_alignment", self._check_commit_ci_alignment))
        if check_code_quality_consistency:
            checks.append(("code_quality_consistency", self._check_code_quality_consistency))
        if check_documentation_consistency:
            checks.append(("documentation_consistency", self._check_documentation_consistency))
        if check_config_consistency:
            checks.append(("config_consistency", self._check_config_consistency))
        return checks

    async def _run_check(
        self,
        check_name: str,
        check_func: Callable[[], tuple[list[InfrastructureIssue], list[str]]],
        issues: list[InfrastructureIssue],
        recommendations: list[str],
        checks_performed: dict[str, bool],
    ) -> None:
        """Run a validation check and update results.

        Args:
            check_name: Name of the check
            check_func: Async function that returns (issues, recommendations)
            issues: List to extend with found issues
            recommendations: List to extend with recommendations
            checks_performed: Dictionary to update with check results
        """
        check_issues, check_recommendations = await check_func()
        issues.extend(check_issues)
        recommendations.extend(check_recommendations)
        checks_performed[check_name] = len(check_issues) == 0

    async def _check_commit_ci_alignment(
        self,
    ) -> tuple[list[InfrastructureIssue], list[str]]:
        """Check commit prompt vs CI workflow alignment.

        Returns:
            Tuple of (issues, recommendations)
        """
        issues: list[InfrastructureIssue] = []
        recommendations: list[str] = []

        missing_file_issue = self._check_missing_files()
        if missing_file_issue:
            issues.append(missing_file_issue)
            return issues, recommendations

        ci_checks = await self._extract_ci_checks()
        commit_steps = await self._extract_commit_steps()
        missing_checks = self._find_missing_checks(ci_checks, commit_steps)

        for check in missing_checks:
            issues.append(self._create_missing_check_issue(check))

        if missing_checks:
            recommendations.append(
                "Synchronize commit prompt with CI workflow requirements"
            )

        return issues, recommendations

    def _check_missing_files(self) -> InfrastructureIssue | None:
        """Check if required files exist.

        Returns:
            Issue if file is missing, None otherwise
        """
        if not self.ci_workflow_path.exists():
            return {
                "type": "missing_file",
                "severity": "high",
                "description": "CI workflow file not found",
                "location": str(self.ci_workflow_path),
                "suggestion": "Create CI workflow file",
                "ci_check": None,
                "missing_in_commit": False,
            }
        if not self.commit_prompt_path.exists():
            return {
                "type": "missing_file",
                "severity": "high",
                "description": "Commit prompt file not found",
                "location": str(self.commit_prompt_path),
                "suggestion": "Create commit prompt file",
                "ci_check": None,
                "missing_in_commit": False,
            }
        return None

    def _create_missing_check_issue(self, check: dict[str, str]) -> InfrastructureIssue:
        """Create issue for missing check.

        Args:
            check: Check dictionary with name and description

        Returns:
            Infrastructure issue dictionary
        """
        return {
            "type": "missing_check",
            "severity": "high",
            "description": f"Commit prompt missing check: {check['name']}",
            "location": str(self.commit_prompt_path),
            "suggestion": f"Add {check['name']} check step to commit prompt",
            "ci_check": check["name"],
            "missing_in_commit": True,
        }

    async def _extract_ci_checks(self) -> list[dict[str, str]]:
        """Extract check steps from CI workflow.

        Returns:
            List of check dictionaries with name and description
        """
        checks: list[dict[str, str]] = []

        if yaml is None:
            return checks

        try:
            content = self.ci_workflow_path.read_text()
            workflow = yaml.safe_load(content)

            if "jobs" not in workflow:
                return checks

            for _job_name, job_config in workflow["jobs"].items():
                if "steps" not in job_config:
                    continue

                for step in job_config["steps"]:
                    if "name" in step:
                        step_name = step["name"]
                        step_run = step.get("run", "")

                        check_name = self._normalize_check_name(step_name)
                        checks.append(
                            {
                                "name": check_name,
                                "description": step_name,
                                "run": step_run,
                            }
                        )
        except Exception:
            pass

        return checks

    async def _extract_commit_steps(self) -> list[dict[str, str]]:
        """Extract procedure steps from commit prompt.

        Returns:
            List of step dictionaries with name and description
        """
        steps: list[dict[str, str]] = []

        try:
            content = self.commit_prompt_path.read_text()

            step_pattern = r"(\d+)\.\s+\*\*([^*]+)\*\*[^\n]*\n((?:[^\n]+\n)*)"
            matches = re.finditer(step_pattern, content)

            for match in matches:
                step_num = match.group(1)
                step_name = match.group(2).strip()
                step_content = match.group(3).strip()

                normalized_name = self._normalize_check_name(step_name)
                steps.append(
                    {
                        "name": normalized_name,
                        "description": step_name,
                        "content": step_content,
                        "number": step_num,
                    }
                )
        except Exception:
            pass

        return steps

    def _normalize_check_name(self, name: str) -> str:
        """Normalize check name for comparison.

        Args:
            name: Original check name

        Returns:
            Normalized check name
        """
        normalized = name.lower()
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip()

        return normalized

    def _find_missing_checks(
        self, ci_checks: list[dict[str, str]], commit_steps: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Find CI checks missing from commit prompt.

        Args:
            ci_checks: List of CI check dictionaries
            commit_steps: List of commit step dictionaries

        Returns:
            List of missing check dictionaries
        """
        missing: list[dict[str, str]] = []

        commit_step_names = {step["name"] for step in commit_steps}

        important_checks = [
            "check formatting",
            "lint",
            "type check",
            "check file sizes",
            "check function lengths",
            "run tests",
        ]

        for check in ci_checks:
            check_name = check["name"]
            if check_name in important_checks and check_name not in commit_step_names:
                missing.append(check)

        return missing

    async def _check_code_quality_consistency(
        self,
    ) -> tuple[list[InfrastructureIssue], list[str]]:
        """Check code quality standards consistency.

        Returns:
            Tuple of (issues, recommendations)
        """
        issues: list[InfrastructureIssue] = []
        recommendations: list[str] = []

        scripts_dir = self.project_root / "scripts"
        required_scripts = [
            "check_file_sizes.py",
            "check_function_lengths.py",
        ]

        for script_name in required_scripts:
            script_path = scripts_dir / script_name
            if not script_path.exists():
                issues.append(
                    {
                        "type": "missing_script",
                        "severity": "medium",
                        "description": f"Required script not found: {script_name}",
                        "location": str(script_path),
                        "suggestion": f"Create {script_name} script",
                        "ci_check": None,
                        "missing_in_commit": False,
                    }
                )

        if issues:
            recommendations.append(
                "Ensure all code quality check scripts exist and are executable"
            )

        return issues, recommendations

    async def _check_documentation_consistency(
        self,
    ) -> tuple[list[InfrastructureIssue], list[str]]:
        """Check documentation consistency.

        Returns:
            Tuple of (issues, recommendations)
        """
        issues: list[InfrastructureIssue] = []
        recommendations: list[str] = []

        readme_path = self.project_root / "README.md"
        if not readme_path.exists():
            issues.append(
                {
                    "type": "missing_documentation",
                    "severity": "low",
                    "description": "README.md not found",
                    "location": str(readme_path),
                    "suggestion": "Create README.md with project documentation",
                    "ci_check": None,
                    "missing_in_commit": False,
                }
            )

        if issues:
            recommendations.append("Ensure project documentation is complete")

        return issues, recommendations

    async def _check_config_consistency(
        self,
    ) -> tuple[list[InfrastructureIssue], list[str]]:
        """Check configuration consistency.

        Returns:
            Tuple of (issues, recommendations)
        """
        issues: list[InfrastructureIssue] = []
        recommendations: list[str] = []

        config_dir = self.project_root / ".cortex"
        required_configs = [
            "validation.json",
            "optimization.json",
        ]

        for config_name in required_configs:
            config_path = config_dir / config_name
            if not config_path.exists():
                issues.append(
                    {
                        "type": "missing_config",
                        "severity": "medium",
                        "description": f"Configuration file not found: {config_name}",
                        "location": str(config_path),
                        "suggestion": f"Create {config_name} configuration file",
                        "ci_check": None,
                        "missing_in_commit": False,
                    }
                )

        if issues:
            recommendations.append(
                "Ensure all required configuration files exist and are properly configured"
            )

        return issues, recommendations
