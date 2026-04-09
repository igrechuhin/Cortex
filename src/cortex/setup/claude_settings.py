from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.setup.hook_models import (
    CommandHookEntry,
    HookCondition,
    HookConditionPayload,
    HookType,
)


class ClaudeSettingsError(ValueError):
    pass


def merge_post_tool_use_edit_hook(
    settings: dict[str, object],
    *,
    command: str,
    condition: HookCondition | None = None,
    once: bool = False,
) -> tuple[dict[str, object], bool]:
    if not command.strip():
        raise ClaudeSettingsError("command must be non-empty")

    post_tool_use = get_or_create_post_tool_use_list(settings)
    matcher_value = _resolve_matcher(condition)

    matcher_entry, matcher_entry_idx = find_post_tool_use_matcher_entry(
        post_tool_use, matcher=matcher_value
    )
    if matcher_entry is None:
        post_tool_use.append(
            _new_post_tool_use_entry(
                command, matcher=matcher_value, condition=condition, once=once
            )
        )
        return (settings, True)

    changed = _ensure_command_hook(
        matcher_entry, command=command, condition=condition, once=once
    )
    if changed:
        post_tool_use[matcher_entry_idx] = matcher_entry
    return (settings, changed)


def _resolve_matcher(condition: HookCondition | None) -> str:
    return condition.to_matcher_string() if condition is not None else "Edit"


def get_or_create_post_tool_use_list(settings: dict[str, object]) -> list[object]:
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
        return post_tool_use
    if isinstance(post_tool_use_value, list):
        return cast(list[object], post_tool_use_value)
    raise ClaudeSettingsError('"hooks.PostToolUse" must be an array when present')


def ensure_post_edit_hook_in_project_claude_settings(
    project_root: Path, *, command: str, condition: HookCondition | None = None
) -> bool:
    settings_path = project_root / ".claude" / "settings.json"
    settings = load_settings_or_empty(settings_path)
    merged, changed = merge_post_tool_use_edit_hook(
        settings, command=command, condition=condition
    )
    if not changed and settings_path.exists():
        return False
    _ = settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return True


def write_once_hook(
    settings_path: Path,
    command: str,
    matcher: str = "Edit",
    condition: HookCondition | None = None,
) -> None:
    settings = load_settings_or_empty(settings_path)
    effective_condition = (
        condition if condition is not None else _condition_from_matcher(matcher)
    )
    merged, changed = merge_post_tool_use_edit_hook(
        settings, command=command, condition=effective_condition, once=True
    )
    if not changed and settings_path.exists():
        return
    _ = settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def write_prompt_hook(
    settings_path: Path,
    matcher: str,
    prompt: str,
    *,
    model: str | None = None,
    timeout: int | None = None,
    status_message: str | None = None,
) -> None:
    from cortex.setup.claude_settings_prompt_agent import write_prompt_hook as _impl

    _impl(
        settings_path=settings_path,
        matcher=matcher,
        prompt=prompt,
        model=model,
        timeout=timeout,
        status_message=status_message,
    )


def write_agent_hook(
    settings_path: Path,
    matcher: str,
    prompt: str,
    *,
    model: str | None = None,
    timeout: int | None = None,
    status_message: str | None = None,
) -> None:
    from cortex.setup.claude_settings_prompt_agent import write_agent_hook as _impl

    _impl(
        settings_path=settings_path,
        matcher=matcher,
        prompt=prompt,
        model=model,
        timeout=timeout,
        status_message=status_message,
    )


def remove_once_hooks(settings_path: Path) -> int:
    settings = load_settings_or_empty(settings_path)
    hooks_value = settings.get("hooks")
    if not isinstance(hooks_value, dict):
        return 0
    hooks = cast(dict[str, object], hooks_value)

    post_tool_use_value = hooks.get("PostToolUse")
    if not isinstance(post_tool_use_value, list):
        return 0

    post_tool_use = cast(list[object], post_tool_use_value)
    removed_count = _remove_once_hooks_from_entries(post_tool_use)
    if removed_count == 0:
        return 0

    _ = settings_path.write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )
    return removed_count


def _remove_once_hooks_from_entries(post_tool_use: list[object]) -> int:
    removed_count = 0
    for entry in post_tool_use:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, object], entry)
        hook_entries_value = entry_dict.get("hooks")
        if not isinstance(hook_entries_value, list):
            continue
        hook_entries = cast(list[object], hook_entries_value)

        filtered_hooks, entry_removed = _filter_non_once_hooks(hook_entries)
        removed_count += entry_removed
        entry_dict["hooks"] = filtered_hooks
    return removed_count


def _filter_non_once_hooks(hook_entries: list[object]) -> tuple[list[object], int]:
    filtered_hooks: list[object] = []
    removed_count = 0
    for hook in hook_entries:
        if not isinstance(hook, dict):
            filtered_hooks.append(hook)
            continue
        hook_dict = cast(dict[str, object], hook)
        if _is_once_value(hook_dict):
            removed_count += 1
            continue
        filtered_hooks.append(cast(dict[str, object], hook))
    return (filtered_hooks, removed_count)


def load_settings_or_empty(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClaudeSettingsError(f"Invalid JSON in {path}") from exc
    if not isinstance(parsed, dict):
        raise ClaudeSettingsError(f"Expected JSON object in {path}")
    return cast(dict[str, object], parsed)


def _condition_from_matcher(matcher: str) -> HookCondition:
    normalized_matcher = matcher.strip()
    if not normalized_matcher:
        raise ClaudeSettingsError("matcher must be non-empty")
    if normalized_matcher.endswith(")") and "(" in normalized_matcher:
        open_paren_idx = normalized_matcher.find("(")
        tool = normalized_matcher[:open_paren_idx].strip()
        pattern = normalized_matcher[open_paren_idx + 1 : -1].strip()
        if not tool:
            raise ClaudeSettingsError("matcher tool must be non-empty")
        return HookCondition(tool=tool, pattern=pattern or None)
    return HookCondition(tool=normalized_matcher)


def find_post_tool_use_matcher_entry(
    post_tool_use: list[object], *, matcher: str
) -> tuple[dict[str, object] | None, int]:
    for idx, entry in enumerate(post_tool_use):
        if not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, object], entry)
        if entry_dict.get("matcher") == matcher:
            return (entry_dict, idx)
    return (None, -1)


def _new_post_tool_use_entry(
    command: str, *, matcher: str, condition: HookCondition | None, once: bool
) -> dict[str, object]:
    return {
        "matcher": matcher,
        "hooks": [
            _command_hook_payload(command=command, condition=condition, once=once)
        ],
    }


def _ensure_command_hook(
    entry: dict[str, object],
    *,
    command: str,
    condition: HookCondition | None,
    once: bool,
) -> bool:
    hooks_value = entry.get("hooks")
    if hooks_value is None:
        entry["hooks"] = [
            _command_hook_payload(command=command, condition=condition, once=once)
        ]
        return True
    if not isinstance(hooks_value, list):
        raise ClaudeSettingsError(
            '"hooks.PostToolUse[].hooks" must be an array when present'
        )

    hooks_list = cast(list[object], hooks_value)
    existing_idx = _find_command_hook_index(hooks_list, command=command, once=once)
    if existing_idx >= 0:
        return _merge_conditions_into_existing_hook(
            hooks_list, index=existing_idx, condition=condition
        )
    hooks_list.append(
        _command_hook_payload(command=command, condition=condition, once=once)
    )
    entry["hooks"] = hooks_list
    return True


def _command_hook_payload(
    *, command: str, condition: HookCondition | None, once: bool
) -> dict[str, object]:
    payload = CommandHookEntry(
        type=HookType.COMMAND, command=command, once=once
    ).model_dump()
    if condition is None:
        return payload

    pattern = condition.pattern.strip() if condition.pattern is not None else None
    if not pattern:
        return payload

    # AI: Keep the forward-compatible matcher metadata so Claude can scope hook firing.
    payload["conditions"] = [
        HookConditionPayload(tool=condition.tool.strip(), pattern=pattern).model_dump()
    ]
    return payload


def _find_command_hook_index(
    hooks_list: list[object], *, command: str, once: bool
) -> int:
    for idx, hook in enumerate(hooks_list):
        if not isinstance(hook, dict):
            continue
        hook_dict = cast(dict[str, object], hook)
        if (
            hook_dict.get("type") == "command"
            and hook_dict.get("command") == command
            and _is_once_value(hook_dict) is once
        ):
            return idx
    return -1


def _is_once_value(hook: dict[str, object]) -> bool:
    once_value = hook.get("once")
    return once_value is True


def _merge_conditions_into_existing_hook(
    hooks_list: list[object], *, index: int, condition: HookCondition | None
) -> bool:
    if condition is None:
        return False

    pattern = condition.pattern.strip() if condition.pattern is not None else None
    if not pattern:
        return False

    existing_hook_value = hooks_list[index]
    if not isinstance(existing_hook_value, dict):
        return False
    existing_hook = cast(dict[str, object], existing_hook_value)
    if existing_hook.get("conditions") is not None:
        return False

    # AI: Backfill conditions for legacy command hooks without duplicating entries.
    existing_hook["conditions"] = [
        HookConditionPayload(tool=condition.tool.strip(), pattern=pattern).model_dump()
    ]
    hooks_list[index] = existing_hook
    return True
