"""Unit tests for ResponseFormat enum and JSON serialization."""

from __future__ import annotations

from pydantic import BaseModel

from cortex.core.models import ResponseFormat


class _PayloadWithResponseFormat(BaseModel):
    """Minimal Pydantic model for serialization tests."""

    response_format: ResponseFormat


class TestResponseFormatEnum:
    """Test ResponseFormat enum definition and values."""

    def test_enum_has_exactly_two_members(self) -> None:
        """ResponseFormat must have exactly CONCISE and DETAILED."""
        assert len(ResponseFormat) == 2
        assert set(ResponseFormat) == {
            ResponseFormat.CONCISE,
            ResponseFormat.DETAILED,
        }

    def test_concise_value(self) -> None:
        """CONCISE serializes to string 'concise'."""
        assert ResponseFormat.CONCISE.value == "concise"

    def test_detailed_value(self) -> None:
        """DETAILED serializes to string 'detailed'."""
        assert ResponseFormat.DETAILED.value == "detailed"

    def test_coercion_from_string(self) -> None:
        """ResponseFormat('concise') and ResponseFormat('detailed') work."""
        assert ResponseFormat("concise") == ResponseFormat.CONCISE
        assert ResponseFormat("detailed") == ResponseFormat.DETAILED


class TestResponseFormatPydanticSerialization:
    """Test that Pydantic serializes ResponseFormat to JSON strings."""

    def test_model_dump_emits_concise_string(self) -> None:
        """A model with response_format CONCISE serializes to 'concise' in JSON."""
        obj = _PayloadWithResponseFormat(response_format=ResponseFormat.CONCISE)
        data = obj.model_dump(mode="json")
        assert data["response_format"] == "concise"

    def test_model_dump_emits_detailed_string(self) -> None:
        """A model with response_format DETAILED serializes to 'detailed' in JSON."""
        obj = _PayloadWithResponseFormat(response_format=ResponseFormat.DETAILED)
        data = obj.model_dump(mode="json")
        assert data["response_format"] == "detailed"

    def test_model_validate_json_coerces_string(self) -> None:
        """JSON with string response_format is parsed and coerced to enum."""
        obj = _PayloadWithResponseFormat.model_validate_json(
            '{"response_format": "concise"}'
        )
        assert obj.response_format == ResponseFormat.CONCISE
        assert obj.response_format.value == "concise"
