from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import HOOK_DEFAULT_MODEL
from cortex.setup.claude_settings import (
    ClaudeSettingsError,
    find_post_tool_use_matcher_entry,
    get_or_create_post_tool_use_list,
    load_settings_or_empty,
)
from cortex.setup.hook_models import (
    AgentHookEntry,
    HookEntry,
    HookType,
    PromptHookEntry,
)


def write_prompt_hook(
    settings_path: Path,
    matcher: str,
    prompt: str,
    *,
    model: str | None = None,
    timeout: int | None = None,
    status_message: str | None = None,
) -> None:
    _write_prompt_or_agent_hook(
        settings_path=settings_path,
        matcher=matcher,
        hook_type=HookType.PROMPT,
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
    _write_prompt_or_agent_hook(
        settings_path=settings_path,
        matcher=matcher,
        hook_type=HookType.AGENT,
        prompt=prompt,
        model=model,
        timeout=timeout,
        status_message=status_message,
    )


def _write_prompt_or_agent_hook(
    *,
    settings_path: Path,
    matcher: str,
    hook_type: HookType,
    prompt: str,
    model: str | None,
    timeout: int | None,
    status_message: str | None,
) -> None:
    normalized_matcher, normalized_prompt = _validated_prompt_hook_inputs(
        matcher=matcher, prompt=prompt, hook_type=hook_type
    )
    _upsert_prompt_or_agent_hook(
        settings_path=settings_path,
        normalized_matcher=normalized_matcher,
        hook_type=hook_type,
        normalized_prompt=normalized_prompt,
        model=model,
        timeout=timeout,
        status_message=status_message,
    )


def _validated_prompt_hook_inputs(
    *, matcher: str, prompt: str, hook_type: HookType
) -> tuple[str, str]:
    _validate_prompt_or_agent_hook_type(hook_type)
    return (_validated_matcher(matcher), _validated_prompt(prompt))


def _upsert_prompt_or_agent_hook(
    *,
    settings_path: Path,
    normalized_matcher: str,
    hook_type: HookType,
    normalized_prompt: str,
    model: str | None,
    timeout: int | None,
    status_message: str | None,
) -> None:
    settings = load_settings_or_empty(settings_path)
    post_tool_use = get_or_create_post_tool_use_list(settings)
    matcher_entry, matcher_entry_idx = _get_or_create_matcher_entry(
        post_tool_use, normalized_matcher
    )

    changed = _ensure_prompt_or_agent_hook(
        matcher_entry,
        hook_type=hook_type,
        prompt=normalized_prompt,
        model=model,
        timeout=timeout,
        status_message=status_message,
    )
    _write_prompt_or_agent_hook_if_changed(
        changed=changed,
        settings_path=settings_path,
        settings=settings,
        post_tool_use=post_tool_use,
        matcher_entry_idx=matcher_entry_idx,
        matcher_entry=matcher_entry,
    )


def _ensure_prompt_or_agent_hook(
    entry: dict[str, object],
    *,
    hook_type: HookType,
    prompt: str,
    model: str | None,
    timeout: int | None,
    status_message: str | None,
) -> bool:
    hooks_list = _get_or_create_entry_hooks_list(entry)
    if (
        _find_prompt_or_agent_hook_index(hooks_list, hook_type=hook_type, prompt=prompt)
        >= 0
    ):
        return False

    hooks_list.append(
        _prompt_or_agent_hook_payload(
            hook_type=hook_type,
            prompt=prompt,
            model=model,
            timeout=timeout,
            status_message=status_message,
        )
    )
    entry["hooks"] = hooks_list
    return True


def _validated_matcher(matcher: str) -> str:
    normalized_matcher = matcher.strip()
    if not normalized_matcher:
        raise ClaudeSettingsError("matcher must be non-empty")
    return normalized_matcher


def _validated_prompt(prompt: str) -> str:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ClaudeSettingsError("prompt must be non-empty")
    return normalized_prompt


def _validate_prompt_or_agent_hook_type(hook_type: HookType) -> None:
    if hook_type not in {HookType.PROMPT, HookType.AGENT}:
        raise ClaudeSettingsError("hook type must be prompt or agent")


def _get_or_create_matcher_entry(
    post_tool_use: list[object], matcher: str
) -> tuple[dict[str, object], int]:
    matcher_entry, matcher_entry_idx = find_post_tool_use_matcher_entry(
        post_tool_use, matcher=matcher
    )
    if matcher_entry is not None:
        return (matcher_entry, matcher_entry_idx)

    new_entry: dict[str, object] = {"matcher": matcher, "hooks": []}
    post_tool_use.append(new_entry)
    return (new_entry, len(post_tool_use) - 1)


def _get_or_create_entry_hooks_list(entry: dict[str, object]) -> list[object]:
    hooks_value = entry.get("hooks")
    if hooks_value is None:
        hooks_list: list[object] = []
        entry["hooks"] = hooks_list
        return hooks_list
    if not isinstance(hooks_value, list):
        raise ClaudeSettingsError(
            '"hooks.PostToolUse[].hooks" must be an array when present'
        )
    return cast(list[object], hooks_value)


def _persist_updated_settings(
    *,
    settings_path: Path,
    settings: dict[str, object],
    post_tool_use: list[object],
    matcher_entry_idx: int,
    matcher_entry: dict[str, object],
) -> None:
    post_tool_use[matcher_entry_idx] = matcher_entry
    _ = settings_path.parent.mkdir(parents=True, exist_ok=True)
    _ = settings_path.write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )


def _write_prompt_or_agent_hook_if_changed(
    *,
    changed: bool,
    settings_path: Path,
    settings: dict[str, object],
    post_tool_use: list[object],
    matcher_entry_idx: int,
    matcher_entry: dict[str, object],
) -> None:
    if not changed:
        return
    _persist_updated_settings(
        settings_path=settings_path,
        settings=settings,
        post_tool_use=post_tool_use,
        matcher_entry_idx=matcher_entry_idx,
        matcher_entry=matcher_entry,
    )


def _find_prompt_or_agent_hook_index(
    hooks_list: list[object], *, hook_type: HookType, prompt: str
) -> int:
    for idx, hook in enumerate(hooks_list):
        if not isinstance(hook, dict):
            continue
        hook_dict = cast(dict[str, object], hook)
        if (
            hook_dict.get("type") == hook_type.value
            and hook_dict.get("prompt") == prompt
        ):
            return idx
    return -1


def _prompt_or_agent_hook_payload(
    *,
    hook_type: HookType,
    prompt: str,
    model: str | None,
    timeout: int | None,
    status_message: str | None,
) -> dict[str, object]:
    model_value = model if model is not None else HOOK_DEFAULT_MODEL
    entry: HookEntry
    if hook_type == HookType.PROMPT:
        entry = PromptHookEntry(
            type=HookType.PROMPT,
            prompt=prompt,
            model=model_value,
            timeout=timeout,
            status_message=status_message,
        )
    elif hook_type == HookType.AGENT:
        entry = AgentHookEntry(
            type=HookType.AGENT,
            prompt=prompt,
            model=model_value,
            timeout=timeout,
            status_message=status_message,
        )
    else:
        raise ClaudeSettingsError("hook type must be prompt or agent")
    return entry.model_dump()
