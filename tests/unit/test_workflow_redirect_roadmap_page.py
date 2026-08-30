"""Tests for the roadmap-page refresh instruction on workflow-superseded prompts."""

from pathlib import Path

from cortex.tools.synapse.prompts_registration import workflow_redirect_content


class TestWorkflowRedirectRoadmapPage:
    """A prompt superseded by a .wf.js script never delivers its own markdown.

    A refresh step written into commit.md or fix.md would therefore never run, and the
    workflow's subagents cannot publish either — the Artifact tool is not in their toolsets.
    The instruction has to ride on the redirect the orchestrating session receives.
    """

    def test_redirect_omits_refresh_by_default(self) -> None:
        """Prompts that do not opt in keep the original, unchanged redirect."""
        # Arrange / Act
        content = workflow_redirect_content(Path("/p/do.wf.js"))

        # Assert
        assert "Workflow tool" in content
        assert "roadmap-page.md" not in content

    def test_redirect_appends_refresh_when_opted_in(self) -> None:
        """commit/fix opt in via the manifest and must carry the refresh instruction."""
        # Arrange / Act
        content = workflow_redirect_content(
            Path("/p/commit.wf.js"), refresh_roadmap_page=True
        )

        # Assert
        assert "Workflow tool" in content
        assert ".cortex/synapse/prompts/roadmap-page.md" in content
        # The redirect must still lead with running the workflow, not the refresh.
        assert content.index("Workflow tool") < content.index("roadmap-page.md")

    def test_refresh_instruction_permits_skipping_a_noop_run(self) -> None:
        """A run that changed no memory-bank file should not force a republish."""
        # Arrange / Act
        content = workflow_redirect_content(
            Path("/p/fix.wf.js"), refresh_roadmap_page=True
        )

        # Assert
        assert "Skip it only if" in content
