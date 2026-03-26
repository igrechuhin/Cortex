from __future__ import annotations


class HookTemplates:
    _POST_EDIT_BY_LANGUAGE: dict[str, str] = {
        "python": "python3 -m pytest tests/ --timeout=30 -x -q 2>&1 | tail -20",
        "swift": "swift build 2>&1 | tail -20",
        "typescript": "npm test --if-present 2>&1 | tail -20",
        "javascript": "npm test --if-present 2>&1 | tail -20",
        "rust": "cargo test 2>&1 | tail -20",
        "go": "go test ./... 2>&1 | tail -20",
        "java": "./mvnw test -q 2>&1 | tail -20",
    }

    @classmethod
    def get_post_edit_hook(cls, language: str) -> str | None:
        normalized = language.strip().lower()
        return cls._POST_EDIT_BY_LANGUAGE.get(normalized)
