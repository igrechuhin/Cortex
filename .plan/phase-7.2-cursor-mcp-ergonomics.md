# Phase 7.2: Cursor-Friendly MCP Development Plan

## Executive Summary

This plan captures all Cursor + MCP + Pyright recommendations and describes how to roll them out quickly without changing the core architecture. It focuses on predictable diagnostics, typed MCP boundaries, pure helper patterns, JSON modeling, interpreter alignment, and documentation updates.

## Goals

- Achieve predictable, low-noise Pyright diagnostics for MCP development while keeping strictness.
- Standardize typed MCP handler boundaries and pure helper patterns across all tool modules.
- Ensure JSON payloads are modeled with `TypedDict` and dataclasses where structure is known.
- Align Cursor, Pyright, and runtime on the same `.venv` interpreter.
- Encode all practices into `.cursor/rules`, `AGENTS.md`, and `CLAUDE.md` so future generations follow them by default.

## Tasks

1. **Pyright configuration alignment**

   - Confirm `pyrightconfig.json` uses:
     - `"typeCheckingMode": "strict"` and `"pythonVersion": "3.13"`.
     - `reportUnknownMemberType`, `reportUnknownArgumentType`, `reportUnknownVariableType` set to `"warning"`.
     - `reportUntypedFunctionDecorator`, `reportUntypedClassDecorator` set to `"none"`.
   - Keep all other strict settings unchanged.

2. **Rule updates for MCP + Cursor ergonomics**

   - Extend `python-mcp-development.mdc` with:
     - Typed MCP handler boundary requirements.
     - Thin handler + pure helper pattern.
     - `TypedDict`-based JSON modeling examples.
     - Pyright configuration notes specific to MCP development.
   - Document the same Pyright behavior in `python-coding-standards.mdc` at a high level.

3. **Agent and IDE guidance alignment**

   - Update `AGENTS.md` with a `Cursor + MCP Development Practices` section covering:
     - `.venv/bin/python` interpreter selection.
     - Typed MCP boundaries and pure helper usage.
     - `TypedDict` for JSON payloads.
     - Refactor preference for pure helpers.
   - Update `CLAUDE.md` with a short section describing:
     - Interpreter selection for IDEs.
     - Expected shape of MCP handlers (typed boundaries, thin async orchestrators).
     - Use of `TypedDict` and dataclasses at protocol edges.

4. **Code-level rollout (MCP handlers)**

   - Inventory all `@mcp.tool()` handlers under `src/cortex/tools/`.
   - For each handler, ensure:
     - Parameters and return types are fully annotated with concrete types or `TypedDict`/dataclasses.
     - The body is refactored to delegate to one or more pure helper functions.
   - Keep each helper ≤30 lines and each file ≤400 lines, following existing constraints.

5. **JSON payload modeling pass**

   - Identify all places where MCP handlers accept or return `dict`-shaped JSON.
   - Introduce `TypedDict` models for request/response structures where keys are known.
   - Replace `dict[str, object]` with more specific `TypedDict` or concrete types wherever possible.

6. **Interpreter and tooling verification**

   - In Cursor and other IDEs, verify the configured Python interpreter is `.venv/bin/python`.
   - Re-index the workspace so Pyright, completions, and MCP discovery share the same environment.
   - Optionally add a Ruff configuration (in `pyproject.toml` or `ruff.toml`) matching:

     ```toml
     [tool.ruff]
     line-length = 100
     target-version = "py313"

     [tool.ruff.lint]
     select = ["E", "F", "I", "B", "UP"]
     ignore = ["E501"]
     ```

7. **Validation and documentation sync**

   - Run Pyright to confirm diagnostics match expectations (no new unknown-type or decorator noise).
   - Run tests to ensure no behavioral regressions.
   - Update `.cursor/memory-bank/activeContext.md` and `progress.md` to record completion of this plan.
   - If needed, add a short quick-reference section to `.plan/phase-7.2-quick-reference.md` pointing to this file.

## Success Criteria

- Pyright diagnostics are strict but not noisy for MCP handlers and JSON payloads.
- All MCP tools have explicit, typed boundaries and rely on small, pure helpers for core logic.
- JSON payload shapes are modeled with `TypedDict` or dataclasses wherever structure is known.
- Cursor, Pyright, and the runtime use the same `.venv` interpreter.
- Future code generations automatically follow these practices due to updated rules and agent docs.
