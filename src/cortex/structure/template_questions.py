#!/usr/bin/env python3
"""
Interactive setup questions for template manager (Phase 8).

Builds question lists for project setup interviews.
"""

from cortex.core.models import ModelDict


def build_interactive_setup_questions() -> list[ModelDict]:
    """Build all questions for interactive project setup.

    Returns:
        List of question dictionaries for the setup interview.
    """
    questions: list[ModelDict] = []
    questions.extend(_build_basic_info_questions())
    questions.extend(_build_technical_questions())
    questions.extend(_build_team_process_questions())
    questions.extend(_build_configuration_questions())
    return questions


def _build_basic_info_questions() -> list[ModelDict]:
    """Build basic project information questions."""
    return [
        {"id": "project_name", "question": "What is the project name?", "type": "text"},
        {
            "id": "project_description",
            "question": "What is this project about? (Brief description)",
            "type": "text",
        },
    ]


def _build_technical_questions() -> list[ModelDict]:
    """Build technical questions."""
    return [
        _build_project_type_question(),
        _build_language_question(),
        _build_frameworks_question(),
    ]


def _build_project_type_question() -> ModelDict:
    """Build project type question."""
    return {
        "id": "project_type",
        "question": "What type of project is this?",
        "type": "choice",
        "options": ["web", "mobile", "backend", "library", "cli", "desktop"],
    }


def _build_language_question() -> ModelDict:
    """Build primary language question."""
    return {
        "id": "primary_language",
        "question": "Primary programming language?",
        "type": "choice",
        "options": [
            "Python",
            "JavaScript",
            "TypeScript",
            "Swift",
            "Rust",
            "Go",
            "Java",
            "C#",
            "Other",
        ],
    }


def _build_frameworks_question() -> ModelDict:
    """Build frameworks question."""
    return {
        "id": "frameworks",
        "question": "Main frameworks/libraries used?",
        "type": "text",
    }


def _build_team_process_questions() -> list[ModelDict]:
    """Build team and process questions."""
    return [
        {
            "id": "team_size",
            "question": "Team size?",
            "type": "choice",
            "options": ["Solo", "2-5", "6-20", "21+"],
        },
        {
            "id": "development_process",
            "question": "Development process?",
            "type": "choice",
            "options": [
                "Agile/Scrum",
                "Kanban",
                "Waterfall",
                "Continuous",
                "Informal",
            ],
        },
    ]


def _build_configuration_questions() -> list[ModelDict]:
    """Build configuration questions."""
    return [
        {
            "id": "use_shared_rules",
            "question": "Use shared rules repository?",
            "type": "boolean",
        },
    ]
