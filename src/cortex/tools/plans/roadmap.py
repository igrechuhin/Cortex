"""
Roadmap operations: internal implementation for update_memory_bank.

roadmap_impl is called by update_memory_bank for roadmap_add, roadmap_remove,
roadmap_remove_section. No longer a standalone MCP tool (consolidated).
"""

from __future__ import annotations

from cortex.core.context_logging import MCPContext


def _roadmap_error_invalid_operation(operation: str) -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Invalid operation '{operation}'. Use add_entry, remove_entry, or remove_section.",
        line_inserted=None,
        section=None,
        error="Invalid operation",
    ).model_dump_json()


def _roadmap_error_add_entry_missing() -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="section and entry_text are required when operation is 'add_entry'",
        line_inserted=None,
        section=None,
        error="Missing section or entry_text",
    ).model_dump_json()


def _roadmap_error_remove_entry_missing() -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import RemoveRoadmapEntryResult

    return RemoveRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="entry_contains is required when operation is 'remove_entry'",
        line_removed=None,
        error="Missing entry_contains",
    ).model_dump_json()


def _roadmap_error_remove_section_missing() -> str:
    from cortex.core.constants import MemoryBankFile
    from cortex.core.models import OperationStatus
    from cortex.tools.models import RemoveRoadmapSectionResult

    return RemoveRoadmapSectionResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="section_heading_contains is required when operation is 'remove_section'",
        section_heading=None,
        lines_removed=None,
        error="Missing section_heading_contains",
    ).model_dump_json()


async def _roadmap_handle_add_entry(
    section: str,
    entry_text: str,
    position: str,
    change_description: str | None,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.entries import add_roadmap_entry

    return await add_roadmap_entry(
        section=section,
        entry_text=entry_text,
        position=position,
        change_description=change_description,
        ctx=ctx,
    )


async def _roadmap_handle_remove_entry(
    entry_contains: str,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.entries import remove_roadmap_entry

    return await remove_roadmap_entry(entry_contains=entry_contains, ctx=ctx)


async def _roadmap_handle_remove_section(
    section_heading_contains: str,
    ctx: MCPContext | None,
) -> str:
    from cortex.tools.plans.entries import remove_roadmap_section

    return await remove_roadmap_section(
        section_heading_contains=section_heading_contains,
        ctx=ctx,
    )


async def roadmap_impl(
    operation: str = "add_entry",
    # add_entry params
    section: str | None = None,
    entry_text: str | None = None,
    position: str = "last",
    change_description: str | None = None,
    # remove_entry params
    entry_contains: str | None = None,
    # remove_section params
    section_heading_contains: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Internal: add, remove, or mutate roadmap entries and sections.

    Called by update_memory_bank. Operations: add_entry, remove_entry, remove_section.
    """
    if operation not in ("add_entry", "remove_entry", "remove_section"):
        return _roadmap_error_invalid_operation(operation)
    if operation == "add_entry":
        if section is None or entry_text is None:
            return _roadmap_error_add_entry_missing()
        return await _roadmap_handle_add_entry(
            section, entry_text, position, change_description, ctx
        )
    if operation == "remove_entry":
        if not entry_contains:
            return _roadmap_error_remove_entry_missing()
        return await _roadmap_handle_remove_entry(entry_contains, ctx)
    if operation == "remove_section":
        if not section_heading_contains:
            return _roadmap_error_remove_section_missing()
        return await _roadmap_handle_remove_section(section_heading_contains, ctx)
    return _roadmap_error_invalid_operation(operation)
