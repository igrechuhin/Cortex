from cortex.memory.memory_types import MemoryType, classify_text


def test_classify_text_returns_decision() -> None:
    assert classify_text("we decided to use FastMCP v3") == MemoryType.DECISION


def test_classify_text_returns_preference() -> None:
    assert classify_text("always use Pydantic BaseModel") == MemoryType.PREFERENCE


def test_classify_text_returns_milestone() -> None:
    assert (
        classify_text("completed migration and merged baseline") == MemoryType.MILESTONE
    )


def test_classify_text_returns_problem() -> None:
    assert (
        classify_text("startup failed with error and blocked deploy")
        == MemoryType.PROBLEM
    )


def test_classify_text_defaults_to_status() -> None:
    assert classify_text("3 plans pending with routine updates") == MemoryType.STATUS
