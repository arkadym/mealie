from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import mealie.services.openai.openai as openai_module
from mealie.core import exceptions
from mealie.schema.openai.general import OpenAIText
from mealie.services.openai.openai import OpenAIService


def _make_mock_repos() -> MagicMock:
    provider_settings = MagicMock()
    provider_settings.ai_enabled = True
    provider_settings.default_provider_id = uuid4()
    provider_settings.audio_provider_id = None
    provider_settings.image_provider_id = None

    repos = MagicMock()
    repos.group_id = uuid4()
    repos.group_ai_provider_settings.get_one.return_value = provider_settings
    repos.group_ai_providers.get_one.return_value = MagicMock()
    return repos


class _SettingsStub:
    OPENAI_CUSTOM_PROMPT_DIR: str | None = None


@pytest.fixture()
def settings_stub(tmp_path, monkeypatch):
    s = _SettingsStub()

    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "recipes").mkdir(parents=True)
    default_prompt = prompts_dir / "recipes" / "parse-recipe-ingredients.txt"
    default_prompt.write_text("DEFAULT PROMPT")

    monkeypatch.setattr(OpenAIService, "PROMPTS_DIR", prompts_dir)

    def _fake_get_app_settings():
        return s

    monkeypatch.setattr(openai_module, "get_app_settings", _fake_get_app_settings)
    return s


def test_get_prompt_default_only(settings_stub):
    svc = OpenAIService(_make_mock_repos())
    out = svc.get_prompt("recipes.parse-recipe-ingredients")
    assert out == "DEFAULT PROMPT"


def test_get_prompt_custom_dir_used(settings_stub, tmp_path):
    custom_dir = tmp_path / "custom"
    (custom_dir / "recipes").mkdir(parents=True)
    (custom_dir / "recipes" / "parse-recipe-ingredients.txt").write_text("CUSTOM PROMPT")

    settings_stub.OPENAI_CUSTOM_PROMPT_DIR = str(custom_dir)

    svc = OpenAIService(_make_mock_repos())
    out = svc.get_prompt("recipes.parse-recipe-ingredients")
    assert out == "CUSTOM PROMPT"


def test_get_prompt_custom_empty_falls_back_to_default(settings_stub, tmp_path):
    custom_dir = tmp_path / "custom"
    (custom_dir / "recipes").mkdir(parents=True)
    (custom_dir / "recipes" / "parse-recipe-ingredients.txt").write_text("")

    settings_stub.OPENAI_CUSTOM_PROMPT_DIR = str(custom_dir)
    svc = OpenAIService(_make_mock_repos())
    out = svc.get_prompt("recipes.parse-recipe-ingredients")
    assert out == "DEFAULT PROMPT"


def test_get_prompt_raises_when_no_files(settings_stub, monkeypatch):
    # Point PROMPTS_DIR to an empty temp folder (already done in fixture) but remove default file
    prompts_dir = OpenAIService.PROMPTS_DIR
    for p in prompts_dir.rglob("*.txt"):
        p.unlink()

    svc = OpenAIService(_make_mock_repos())
    with pytest.raises(OSError) as ei:
        svc.get_prompt("recipes.parse-recipe-ingredients")
    assert "Unable to load prompt" in str(ei.value)


def _completion(content=None, tool_arguments=None) -> SimpleNamespace:
    tool_calls = [SimpleNamespace(function=SimpleNamespace(arguments=tool_arguments))] if tool_arguments else None
    message = SimpleNamespace(content=content, tool_calls=tool_calls, function_call=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _stub_raw_response(monkeypatch, svc: OpenAIService, completion: SimpleNamespace) -> None:
    async def _fake_get_raw_response(*args, **kwargs):
        return completion

    monkeypatch.setattr(svc, "_get_raw_response", _fake_get_raw_response)


@pytest.mark.asyncio
async def test_get_response_reads_message_content(settings_stub, monkeypatch):
    svc = OpenAIService(_make_mock_repos())
    _stub_raw_response(monkeypatch, svc, _completion(content='{"text": "hello"}'))

    result = await svc.get_response("prompt", "message", response_schema=OpenAIText, provider=MagicMock())
    assert result is not None
    assert result.text == "hello"


@pytest.mark.asyncio
async def test_get_response_reads_tool_call_payload(settings_stub, monkeypatch):
    """
    Regression: a provider (or gateway) without json_schema support answers with a forced tool
    call, leaving message.content empty. Reading only content discarded a correct response.
    """
    svc = OpenAIService(_make_mock_repos())
    _stub_raw_response(monkeypatch, svc, _completion(content=None, tool_arguments='{"text": "hello"}'))

    result = await svc.get_response("prompt", "message", response_schema=OpenAIText, provider=MagicMock())
    assert result is not None
    assert result.text == "hello"


@pytest.mark.asyncio
async def test_get_response_unwraps_fenced_json(settings_stub, monkeypatch):
    svc = OpenAIService(_make_mock_repos())
    _stub_raw_response(monkeypatch, svc, _completion(content='```json\n{"text": "hello"}\n```'))

    result = await svc.get_response("prompt", "message", response_schema=OpenAIText, provider=MagicMock())
    assert result is not None
    assert result.text == "hello"


@pytest.mark.asyncio
async def test_get_response_raises_on_empty_payload(settings_stub, monkeypatch):
    svc = OpenAIService(_make_mock_repos())
    _stub_raw_response(monkeypatch, svc, _completion(content=None))

    with pytest.raises(exceptions.OpenAIEmptyResponseError):
        await svc.get_response("prompt", "message", response_schema=OpenAIText, provider=MagicMock())


@pytest.mark.asyncio
async def test_get_response_returns_none_without_choices(settings_stub, monkeypatch):
    svc = OpenAIService(_make_mock_repos())
    _stub_raw_response(monkeypatch, svc, SimpleNamespace(choices=[]))

    result = await svc.get_response("prompt", "message", response_schema=OpenAIText, provider=MagicMock())
    assert result is None
