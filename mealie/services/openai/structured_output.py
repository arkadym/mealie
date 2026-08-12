"""
Building a structured-output request for whichever mechanism a provider supports.

OpenAI Structured Outputs (``response_format={"type": "json_schema", ..., "strict": true}``) is
implemented by OpenAI and Azure. Other OpenAI-compatible providers reject it outright — DeepSeek
answers ``400 This response_format type is unavailable now`` — or silently ignore it, as the
Anthropic compatibility layer does.

Each provider therefore declares how it can be asked for structured output, and this module turns
that declaration into request keyword arguments.
"""

import json
from typing import Any

from mealie.schema.group.ai_providers import AIStructuredOutputMode

TOOL_NAME = "format_response"

_SCHEMA_INSTRUCTIONS = """
###
Respond with a single json object and nothing else. No prose, no explanation, no markdown code
fences. It must validate against this json schema:
---

{schema}
"""


def dereference_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Inline every ``$ref`` and drop ``$defs``.

    Pydantic emits ``$defs``/``$ref`` for nested models. Providers vary in how well they handle
    references in tool parameters, and a fully inlined schema is understood everywhere.
    """

    definitions = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = definitions.get(ref.removeprefix("#/$defs/"))
            if target is not None:
                # Preserve any sibling keys (e.g. description) alongside the resolved target
                merged = {**resolve(target), **{k: v for k, v in node.items() if k != "$ref"}}
                return merged

        return {key: resolve(value) for key, value in node.items() if key != "$defs"}

    resolved = resolve(schema)
    return resolved if isinstance(resolved, dict) else schema


def schema_instructions(schema: dict[str, Any]) -> str:
    """
    Prompt text describing the required response shape.

    Used by the modes that cannot send a schema with the request. The literal word "json" is
    required here: DeepSeek rejects ``response_format={"type": "json_object"}`` unless it appears
    in the prompt.
    """

    return _SCHEMA_INSTRUCTIONS.format(schema=json.dumps(schema, separators=(",", ":")))


def build_request(
    mode: AIStructuredOutputMode,
    system_prompt: str,
    response_schema: type,
) -> tuple[str, dict[str, Any], bool]:
    """
    Return ``(system_prompt, request_kwargs, use_parse_helper)`` for the given mode.

    ``use_parse_helper`` selects the OpenAI SDK's ``chat.completions.parse`` (which serialises the
    Pydantic model into a strict json_schema) over plain ``chat.completions.create``.
    """

    if mode == AIStructuredOutputMode.json_schema:
        return system_prompt, {"response_format": response_schema}, True

    schema = dereference_schema(response_schema.model_json_schema())

    if mode == AIStructuredOutputMode.tool_call:
        return (
            system_prompt,
            {
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": TOOL_NAME,
                            "description": "Return the response in the required structure.",
                            "parameters": schema,
                        },
                    }
                ],
                # Deliberately "auto" rather than forcing the tool: DeepSeek's V4 models are
                # always in thinking mode, and thinking mode rejects both "required" and a
                # forced function. With a single tool on offer the model calls it anyway, and
                # a provider that needs the tool forced can disable thinking via request_body.
                "tool_choice": "auto",
            },
            False,
        )

    prompt = f"{system_prompt}\n{schema_instructions(schema)}"

    if mode == AIStructuredOutputMode.json_object:
        return prompt, {"response_format": {"type": "json_object"}}, False

    return prompt, {}, False
