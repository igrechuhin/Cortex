"""Helpers for building markdown lint JSON responses."""

import json


def create_error_response(error_message: str) -> str:
    """Create error response JSON for markdown lint operations."""
    # fmt: off
    return json.dumps(
        {
            "success": False,
            "files_processed": 0,
            "files_fixed": 0,
            "files_unchanged": 0,
            "files_with_errors": 0,
            "results": [],
            "error_message": error_message,
        },
        indent=2,
    )
    # fmt: on


def create_empty_success_response() -> str:
    """Create empty success response JSON for markdown lint operations."""
    # fmt: off
    return json.dumps(
        {
            "success": True,
            "files_processed": 0,
            "files_fixed": 0,
            "files_unchanged": 0,
            "files_with_errors": 0,
            "results": [],
            "error_message": None,
        },
        indent=2,
    )
    # fmt: on
