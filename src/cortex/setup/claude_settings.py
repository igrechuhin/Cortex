from __future__ import annotations

import json
from pathlib import Path
from typing import cast


class ClaudeSettingsError(ValueError):
    pass


def merge_post_tool_use_edit_hook(
    settings: dict[str, object], *, command: str
) -> tuple[dict[str, object], bool]:
    if not command.strip():
        raise ClaudeSettingsError("command must be non-empty")

    hooks_value = settings.get("hooks")
    if hooks_value is None:
        hooks: dict[str, object] = {}
        settings["hooks"] = hooks
    elif isinstance(hooks_value, dict):
        hooks = cast(dict[str, object], hooks_value)
    else:
        raise ClaudeSettingsError('"hooks" must be an object when present')

    post_tool_use_value = hooks.get("PostToolUse")
    if post_tool_use_value is None:
        post_tool_use: list[object] = []
        hooks["PostToolUse"] = post_tool_use
    elif isinstance(post_tool_use_value, list):
        post_tool_use = cast(list[object], post_tool_use_value)
    else:
        raise ClaudeSettingsError('"hooks.PostToolUse" must be an array when present')

    matcher_entry, matcher_entry_idx = _find_post_tool_use_matcher_entry(
        post_tool_use, matcher="Edit"
    )
    if matcher_entry is None:
        post_tool_use.append(_new_post_tool_use_entry(command))
        return (settings, True)

    changed = _ensure_command_hook(matcher_entry, command=command)
    if changed:
        post_tool_use[matcher_entry_idx] = matcher_entry
    return (settings, changed)


def ensure_post_edit_hook_in_project_claude_settings(
    project_root: Path, *, command: str
) -> bool:
    settings_path = project_root / ".claude" / "settings.json"
    settings = _load_settings_or_empty(settings_path)
    merged, changed = merge_post_tool_use_edit_hook(settings, command=command)
    if not changed and settings_path.exists():
        return False
    _ = settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return True


def _load_settings_or_empty(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClaudeSettingsError(f"Invalid JSON in {path}") from exc
    if not isinstance(parsed, dict):
        raise ClaudeSettingsError(f"Expected JSON object in {path}")
    return cast(dict[str, object], parsed)


def _find_post_tool_use_matcher_entry(
    post_tool_use: list[object], *, matcher: str
) -> tuple[dict[str, object] | None, int]:
    for idx, entry in enumerate(post_tool_use):
        if not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, object], entry)
        if entry_dict.get("matcher") == matcher:
            return (entry_dict, idx)
    return (None, -1)


def _new_post_tool_use_entry(command: str) -> dict[str, object]:
    return {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": command}],
    }


def _ensure_command_hook(entry: dict[str, object], *, command: str) -> bool:
    hooks_value = entry.get("hooks")
    if hooks_value is None:
        entry["hooks"] = [{"type": "command", "command": command}]
        return True
    if not isinstance(hooks_value, list):
        raise ClaudeSettingsError(
            '"hooks.PostToolUse[].hooks" must be an array when present'
        )

    hooks_list = cast(list[object], hooks_value)
    if _hooks_list_contains_command(hooks_list, command=command):
        return False
    hooks_list.append({"type": "command", "command": command})
    entry["hooks"] = hooks_list
    return True


def _hooks_list_contains_command(hooks_list: list[object], *, command: str) -> bool:
    for hook in hooks_list:
        if not isinstance(hook, dict):
            continue
        hook_dict = cast(dict[str, object], hook)
        if hook_dict.get("type") == "command" and hook_dict.get("command") == command:
            return True
    return False
