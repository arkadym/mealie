"""
Locating the payload in a chat completion response.

Providers do not agree on where a structured response goes. OpenAI's Structured Outputs put it
in ``message.content``, but a provider (or a gateway sitting in front of one) that lacks
``json_schema`` support commonly satisfies the same request with a forced tool call instead,
leaving ``content`` empty and the payload in ``tool_calls[0].function.arguments``.

Reading only ``content`` therefore discards perfectly good responses. These helpers look in
every place a payload legitimately appears.
"""

import json
import re

RE_CODE_FENCE = re.compile(
    r"^\s*```(?:json|JSON)?\s*\n(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL,
)

_JSON_OPENERS = {"{": "}", "[": "]"}


def extract_payload(message) -> str | None:
    """
    Return the raw payload text from a chat completion message, or None if it carries none.

    Checked in order of preference: message content, then a tool call's arguments, then the
    deprecated function call's arguments.
    """

    if not message:
        return None

    content = getattr(message, "content", None)
    if content and content.strip():
        return content

    for tool_call in getattr(message, "tool_calls", None) or []:
        arguments = getattr(getattr(tool_call, "function", None), "arguments", None)
        if arguments and arguments.strip():
            return arguments

    function_call = getattr(message, "function_call", None)
    arguments = getattr(function_call, "arguments", None)
    if arguments and arguments.strip():
        return arguments

    return None


def strip_code_fences(text: str) -> str:
    """Remove a surrounding markdown code fence, if present."""

    match = RE_CODE_FENCE.match(text)
    return match.group("body") if match else text


def extract_json_span(text: str) -> str | None:
    """
    Return the first complete JSON object or array in the text, or None if there isn't one.

    Used when a provider wraps its JSON in prose. Quoted strings and escapes are respected, so
    braces inside string values don't end the span early.
    """

    for index, char in enumerate(text):
        if char not in _JSON_OPENERS:
            continue

        span = _scan_json_span(text, index, char, _JSON_OPENERS[char])
        if span is not None:
            return span

    return None


def _scan_json_span(text: str, start: int, opener: str, closer: str) -> str | None:
    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def normalize_payload(text: str) -> str:
    """
    Normalize a raw payload into something parseable as JSON.

    Returns the text unchanged when it already parses, so a well-behaved provider costs one
    extra parse and nothing else.
    """

    candidates = [text, strip_code_fences(text)]

    for candidate in candidates:
        stripped = candidate.strip()
        if not stripped:
            continue
        if _is_json(stripped):
            return stripped

    for candidate in candidates:
        span = extract_json_span(candidate)
        if span is not None and _is_json(span):
            return span

    # Nothing parsed; hand back the fence-stripped text so the caller's error mentions the
    # most readable form of what the provider actually sent.
    return strip_code_fences(text).strip()


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True
