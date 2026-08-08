"""Tests for the PHP framework adapter and its XML report parsing."""

import tempfile
from pathlib import Path

from cortex.services.framework_adapters.detection import detect_language_at_path
from cortex.services.framework_adapters.php_adapter import (
    PhpAdapter,
    keyed_file_errors,
    psalm_errors,
)
from cortex.services.framework_adapters.php_parsing import parse_clover, parse_junit

_JUNIT = """<testsuites><testsuite name="s">
<testcase name="ok" class="A"/>
<testcase name="bad" class="A"><failure message="boom"/></testcase>
<testcase name="err" class="B"><error message="fatal"/></testcase>
<testcase name="meh" class="A"><skipped/></testcase>
</testsuite></testsuites>"""

_CLOVER = """<coverage><project>
<file name="{root}/src/A.php"><metrics statements="10" coveredstatements="5"/></file>
<file name="{root}/src/B.php"><metrics statements="10" coveredstatements="0"/></file>
</project></coverage>"""


class TestPhpDetection:
    """PHP must win over JS when both composer.json and package.json exist."""

    def test_composer_and_package_json_detects_php(self) -> None:
        """Arrange a Laravel-style root; act; assert PHP, not JavaScript."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "composer.json").write_text('{"name": "acme/app"}')
            _ = (root / "package.json").write_text('{"devDependencies": {}}')

            result = detect_language_at_path(root)

            assert result is not None
            assert result[0].language == "php"
            assert result[0].build_tool == "composer"

    def test_artisan_alone_detects_php(self) -> None:
        """A Laravel artisan entrypoint is a sufficient PHP marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "artisan").write_text("#!/usr/bin/env php\n")

            result = detect_language_at_path(root)

            assert result is not None
            assert result[0].language == "php"


class TestParseJunit:
    """JUnit XML parsing replaces console scraping."""

    def test_counts_pass_fail_skip_and_messages(self) -> None:
        """Arrange a JUnit report; act; assert per-case counts and messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = Path(tmpdir) / "junit.xml"
            _ = report.write_text(_JUNIT)

            counts = parse_junit(report)

            assert counts is not None
            assert (counts.passed, counts.failed, counts.skipped) == (1, 2, 1)
            assert counts.failures == ["A::bad: boom", "B::err: fatal"]

    def test_missing_report_returns_none(self) -> None:
        """A missing report yields None rather than raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert parse_junit(Path(tmpdir) / "absent.xml") is None

    def test_malformed_report_returns_none(self) -> None:
        """Truncated XML yields None rather than raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = Path(tmpdir) / "junit.xml"
            _ = report.write_text("<testsuites>")

            assert parse_junit(report) is None


class TestParseClover:
    """Clover XML parsing supplies coverage and per-file gaps."""

    def test_overall_and_per_file_coverage(self) -> None:
        """Arrange a two-file Clover report; act; assert totals and gaps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report = root / "clover.xml"
            _ = report.write_text(_CLOVER.format(root=root))

            overall, gaps = parse_clover(report, root)

            assert overall == 0.25
            assert [g.file for g in gaps] == ["src/A.php", "src/B.php"]
            assert gaps[1].lines_uncovered == 10

    def test_missing_report_returns_no_coverage(self) -> None:
        """A missing Clover report degrades to (None, [])."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            assert parse_clover(root / "absent.xml", root) == (None, [])


class TestStaticAnalysisExtractors:
    """Analyser findings come from JSON, never from regex over stdout."""

    def test_phpstan_style_payload(self) -> None:
        """PHPStan/phpcs share a keyed-files JSON shape."""
        payload = {
            "files": {"src/A.php": {"messages": [{"line": 7, "message": "Bad type"}]}}
        }

        assert keyed_file_errors(payload) == ["src/A.php:7: Bad type"]

    def test_psalm_style_payload(self) -> None:
        """Psalm emits a flat list of issues."""
        payload = [{"file_name": "src/A.php", "line_from": 3, "message": "Nope"}]

        assert psalm_errors(payload) == ["src/A.php:3: Nope"]

    def test_unexpected_payloads_yield_no_errors(self) -> None:
        """Unrecognised JSON shapes must not crash the gate."""
        assert keyed_file_errors(["not a dict"]) == []
        assert keyed_file_errors({"files": "wrong"}) == []
        assert psalm_errors({"not": "a list"}) == []


class TestPhpAdapterWithoutToolchain:
    """A PHP project with no installed tools degrades gracefully."""

    def test_missing_runner_reports_error_not_crash(self) -> None:
        """Arrange a bare composer project; act; assert a clean failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "composer.json").write_text("{}")

            result = PhpAdapter(str(root)).run_tests()

            assert result.success is False
            assert result.tests_run == 0
            assert result.errors == ["PHP test runner not installed"]

    def test_missing_analyser_skips_type_check(self) -> None:
        """No phpstan/psalm in vendor/bin means a skipped, passing check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _ = (root / "composer.json").write_text("{}")

            result = PhpAdapter(str(root)).type_check()

            assert result.success is True
            assert result.errors == []
