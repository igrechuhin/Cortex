# Enrich memory bank write tools with validations

## Goal

Protect against broken or corrupted records when writing to the memory bank via Cortex MCP by adding pre-write validations to the tools that perform writes.

## Context

- All memory bank writes go through `manage_file(operation="write")` or `write_file`.
- Both tools share the same implementation path in `file_operations.py` (`_handle_write_operation` → `_execute_write_flow`).
- Existing checks: path validation, “content required”, “file must exist” (no new file creation), roadmap corruption fix for `roadmap.md`, conflict/lock handling.

## Implemented changes

### 1. Pre-write schema validation

- **Where**: `_handle_write_operation` in `src/cortex/tools/file_operations.py`.
- **Behavior**: Before persisting, if a schema exists for the file (e.g. `projectBrief.md`, `activeContext.md`, `progress.md`), the content is validated with `SchemaValidator.validate_file(file_name, content)`.
- **On failure**: Write is aborted and a structured JSON error is returned (`build_schema_validation_error_response`) with `status: "error"`, `file_name`, `validation.errors`, `validation.warnings`, `validation.score`, and a short hint.
- **Schema validator**: Resolved via `get_manager(managers, "schema_validator", SchemaValidator)` in `_dispatch_write_operation`. If the manager is missing or resolution fails, schema validation is skipped (write still allowed).

### 2. Content sanity checks

- **Where**: `validate_write_content()` in `src/cortex/tools/file_operations.py` (used by `_validate_write_request`).
- **Checks**:
  - Content is required (unchanged).
  - **New**: Content must not contain null bytes (`\x00`). Rejects to avoid corrupting text files and downstream tools.

### 3. Helper for schema validation errors

- **Where**: `src/cortex/tools/file_operation_helpers.py`.
- **New**: `build_schema_validation_error_response(file_name, validation_result)` builds the JSON error payload returned when schema validation fails, including errors and warnings for the client to fix the content.

### 4. Tests

- **`validate_write_content`**: New test `test_validate_write_content_rejects_null_bytes` ensures null bytes are rejected.
- **Schema error response**: New test `test_build_schema_validation_error_response` checks the shape of the error JSON (status, file_name, validation.errors, score).
- **Write rejection**: New test `test_manage_file_write_rejected_by_schema_validation` mocks the schema validator to return `valid=False` and asserts the write is rejected (error response, no call to `fs.write_file`).

## Files touched

- `src/cortex/tools/file_operations.py`: imports (`get_manager`, `SchemaValidator`, `build_schema_validation_error_response`), null-byte check in `validate_write_content`, schema validator resolution and pre-write validation in dispatch/handler.
- `src/cortex/tools/file_operation_helpers.py`: import `ValidationResult`, new `build_schema_validation_error_response`.
- `tests/tools/test_file_operations.py`: new tests and imports for validation helpers/models.

## Optional follow-ups

- **Config**: Honor a validation config (e.g. `auto_validate_on_write`) to allow disabling schema validation on write if needed.
- **Other writers**: Any other MCP code that writes memory bank content (e.g. `add_roadmap_entry`, plan completion) that does not go through `manage_file`/`write_file` could call the same validation helpers before writing.
- **Strict vs warn**: Option to allow writes with schema warnings but block only on errors (currently any `valid=False` blocks).
