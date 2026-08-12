import json

from pydantic import Field

from mealie.schema.group.ai_providers import AIStructuredOutputMode
from mealie.schema.openai._base import OpenAIBase
from mealie.services.openai.structured_output import (
    TOOL_NAME,
    build_request,
    dereference_schema,
    schema_instructions,
)


class _Child(OpenAIBase):
    text: str = Field(..., description="child text")


class _Parent(OpenAIBase):
    name: str = Field(..., description="the name")
    children: list[_Child] = Field(default_factory=list, description="the children")


class TestDereferenceSchema:
    def test_inlines_nested_definitions(self):
        schema = dereference_schema(_Parent.model_json_schema())
        assert "$defs" not in json.dumps(schema)
        assert "$ref" not in json.dumps(schema)

    def test_nested_properties_survive(self):
        schema = dereference_schema(_Parent.model_json_schema())
        child = schema["properties"]["children"]["items"]
        assert child["properties"]["text"]["type"] == "string"

    def test_preserves_sibling_keys_on_a_ref(self):
        schema = {
            "$defs": {"Thing": {"type": "object", "properties": {"a": {"type": "string"}}}},
            "properties": {"thing": {"$ref": "#/$defs/Thing", "description": "kept"}},
        }
        resolved = dereference_schema(schema)
        assert resolved["properties"]["thing"]["description"] == "kept"
        assert resolved["properties"]["thing"]["type"] == "object"

    def test_leaves_plain_schema_alone(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        assert dereference_schema(schema) == schema


class TestSchemaInstructions:
    def test_mentions_json_literally(self):
        """DeepSeek rejects json_object mode unless the prompt contains the word 'json'."""
        assert "json" in schema_instructions({"type": "object"})


class TestBuildRequest:
    def test_json_schema_mode_uses_the_parse_helper(self):
        prompt, kwargs, use_parse = build_request(AIStructuredOutputMode.json_schema, "PROMPT", _Parent)
        assert use_parse is True
        assert kwargs == {"response_format": _Parent}
        assert prompt == "PROMPT"

    def test_tool_call_mode_offers_one_tool_without_forcing_it(self):
        """
        tool_choice is deliberately "auto": DeepSeek's V4 models are always in thinking mode,
        and thinking mode rejects both "required" and a named function.
        """
        prompt, kwargs, use_parse = build_request(AIStructuredOutputMode.tool_call, "PROMPT", _Parent)
        assert use_parse is False
        assert prompt == "PROMPT"
        assert kwargs["tool_choice"] == "auto"
        assert len(kwargs["tools"]) == 1

        function = kwargs["tools"][0]["function"]
        assert function["name"] == TOOL_NAME
        assert "$ref" not in json.dumps(function["parameters"])

    def test_json_object_mode_sets_response_format_and_augments_the_prompt(self):
        prompt, kwargs, use_parse = build_request(AIStructuredOutputMode.json_object, "PROMPT", _Parent)
        assert use_parse is False
        assert kwargs == {"response_format": {"type": "json_object"}}
        assert prompt.startswith("PROMPT")
        assert "json" in prompt
        assert "children" in prompt

    def test_text_mode_sends_no_extra_kwargs(self):
        prompt, kwargs, use_parse = build_request(AIStructuredOutputMode.text, "PROMPT", _Parent)
        assert use_parse is False
        assert kwargs == {}
        assert prompt.startswith("PROMPT")
        assert "children" in prompt
