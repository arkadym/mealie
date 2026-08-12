from types import SimpleNamespace

from mealie.services.openai.response_extraction import (
    extract_json_span,
    extract_payload,
    normalize_payload,
    strip_code_fences,
)


def _message(content=None, tool_calls=None, function_call=None) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=tool_calls, function_call=function_call)


def _tool_call(arguments: str | None) -> SimpleNamespace:
    return SimpleNamespace(function=SimpleNamespace(arguments=arguments))


class TestExtractPayload:
    def test_reads_message_content(self):
        assert extract_payload(_message(content='{"a": 1}')) == '{"a": 1}'

    def test_reads_tool_call_when_content_is_none(self):
        """The LiteLLM/DeepSeek case: the schema is satisfied by a forced tool call."""
        message = _message(content=None, tool_calls=[_tool_call('{"a": 1}')])
        assert extract_payload(message) == '{"a": 1}'

    def test_reads_tool_call_when_content_is_blank(self):
        message = _message(content="   \n ", tool_calls=[_tool_call('{"a": 1}')])
        assert extract_payload(message) == '{"a": 1}'

    def test_reads_deprecated_function_call(self):
        message = _message(content=None, function_call=SimpleNamespace(arguments='{"a": 1}'))
        assert extract_payload(message) == '{"a": 1}'

    def test_prefers_content_over_tool_call(self):
        message = _message(content='{"from": "content"}', tool_calls=[_tool_call('{"from": "tool"}')])
        assert extract_payload(message) == '{"from": "content"}'

    def test_skips_empty_tool_calls(self):
        message = _message(content=None, tool_calls=[_tool_call(None), _tool_call("  "), _tool_call('{"a": 1}')])
        assert extract_payload(message) == '{"a": 1}'

    def test_returns_none_when_nothing_present(self):
        assert extract_payload(_message()) is None
        assert extract_payload(_message(content="", tool_calls=[])) is None
        assert extract_payload(None) is None


class TestStripCodeFences:
    def test_strips_json_fence(self):
        assert strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_strips_bare_fence(self):
        assert strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_leaves_unfenced_text_alone(self):
        assert strip_code_fences('{"a": 1}') == '{"a": 1}'

    def test_leaves_inner_backticks_alone(self):
        text = '{"a": "```"}'
        assert strip_code_fences(text) == text


class TestExtractJsonSpan:
    def test_finds_object_surrounded_by_prose(self):
        assert extract_json_span('Sure! Here you go:\n{"a": 1}\nHope that helps.') == '{"a": 1}'

    def test_finds_array(self):
        assert extract_json_span("Here: [1, 2, 3] done") == "[1, 2, 3]"

    def test_handles_nested_structures(self):
        payload = '{"a": {"b": [1, {"c": 2}]}}'
        assert extract_json_span(f"text {payload} text") == payload

    def test_ignores_braces_inside_strings(self):
        payload = '{"a": "not } the end", "b": 1}'
        assert extract_json_span(payload) == payload

    def test_ignores_escaped_quotes(self):
        payload = '{"a": "say \\"hi\\" }", "b": 1}'
        assert extract_json_span(payload) == payload

    def test_returns_none_without_json(self):
        assert extract_json_span("no json here") is None

    def test_returns_none_for_unterminated_json(self):
        assert extract_json_span('{"a": 1') is None


class TestNormalizePayload:
    def test_passes_through_valid_json(self):
        assert normalize_payload('{"a": 1}') == '{"a": 1}'

    def test_unwraps_fenced_json(self):
        assert normalize_payload('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_extracts_json_from_prose(self):
        assert normalize_payload('Certainly! {"a": 1} Let me know.') == '{"a": 1}'

    def test_extracts_json_from_fenced_prose(self):
        raw = 'Here is the recipe:\n\n```json\n{"a": 1}\n```\n\nEnjoy!'
        assert normalize_payload(raw) == '{"a": 1}'

    def test_prefers_whole_payload_over_inner_span(self):
        """A valid document is returned as-is, not reduced to its first nested object."""
        payload = '{"outer": {"inner": 1}}'
        assert normalize_payload(payload) == payload

    def test_returns_readable_text_when_nothing_parses(self):
        assert normalize_payload("I cannot help with that.") == "I cannot help with that."
