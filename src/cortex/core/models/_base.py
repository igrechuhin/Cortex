"""Base models and type aliases for core modules."""

from collections.abc import ItemsView, KeysView, ValuesView

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

# JSON-serializable value type (Python 3.13+ recursive type alias).
type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]

# Common JSON dictionary shape used at JSON boundaries.
type ModelDict = dict[str, JsonValue]


class DictLikeModel(BaseModel):
    """A Pydantic model that supports dict-like access."""

    def __getitem__(self, key: str) -> JsonValue:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data[key]

    def get(self, key: str, default: JsonValue | None = None) -> JsonValue | None:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.get(key, default)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return key in data

    def keys(self) -> KeysView[str]:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.keys()

    def items(self) -> ItemsView[str, JsonValue]:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.items()

    def values(self) -> ValuesView[JsonValue]:
        data: ModelDict = self.model_dump(mode="python", by_alias=True)
        return data.values()


class JsonDict(DictLikeModel):
    """Pydantic model for JSON dictionary structures.

    This model replaces `ModelDict` for type-safe JSON dictionary handling.
    It allows arbitrary keys and values, making it suitable for JSON data.
    Uses extra=EXTRA_ALLOW to accept any keys dynamically.
    Inherits from DictLikeModel to support dict-like access
    (__getitem__, __contains__, etc.).
    """

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    def to_dict(self) -> ModelDict:
        """Convert to plain dictionary."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: ModelDict | dict[str, JsonValue]):
        """Create JsonDict from a dictionary."""
        return cls.model_validate(data)


class JsonList(BaseModel):
    """Pydantic model for JSON list structures."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    items: list[JsonValue] = Field(
        default_factory=lambda: list[JsonValue](), description="List items"
    )

    def to_list(self) -> list[JsonValue]:
        """Convert to plain list."""
        return self.items

    @classmethod
    def from_list(cls, data: list[JsonValue]):
        """Create JsonList from a list."""
        return cls(items=data)
