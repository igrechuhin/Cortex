# Test helpers

Shared utilities and conventions for Cortex tests.

## Canonical imports

Use `tests.helpers.imports` for common validation models, manager types, and exceptions so tests stay consistent and refactors are easier:

```python
from tests.helpers.imports import (
    ValidationResultModel,
    ValidationErrorModel,
    ManagersDict,
    MemoryBankError,
    FileLockTimeoutError,
    FileConflictError,
    FileOperationError,
    MigrationFailedError,
)
```

- **ValidationResultModel** / **ValidationErrorModel**: Pydantic models from `cortex.validation.models` (validation result and error shapes).
- **ManagersDict**: Type from `cortex.managers.types` for manager dictionaries.
- **Exceptions**: Common `cortex.core.exceptions` used in tests (MemoryBankError, FileLockTimeoutError, etc.).

New tests should prefer these re-exports over importing directly from `cortex.*` for these types. Optional migration of existing tests can be done gradually.

## Other helpers

- **types.py**: Type aliases (e.g. `MockManagersDict`, `RawJSONDict`) and small type/assert helpers.
- **tool_call_helpers.py**: Extract tool functions from FastMCP `FunctionTool`, convert results to dicts, type-safe result accessors. **assertion_helpers.py**: Assertions on result dicts (error/message contains, in list). **manager_mocks.py**, **file_fixtures.py**, **data_generators.py**: Reserved for mock/fixture/data helpers.
- **path_helpers.py**: Project and path resolution for tests.
- **managers.py**: Fixtures and builders for manager mocks.
- **schema_fixtures.py** / **fixture_validator.py**: Schema and fixture validation.

## Test templates

`test_templates.py` provides snippet templates for common test patterns:

- **test_error_path_template()**: Error handling (e.g. `pytest.raises`, invalid input).
- **test_edge_case_template()**: Edge cases (empty input, boundaries, None).
- **test_validation_template()**: Validation logic (schema, required fields).

Use `get_all_templates()` to retrieve all snippets. Copy the returned strings into new tests and replace placeholders (`<subject>`, `<Error>`, etc.).
