import httpx
import pytest

from fightnight.otari import Otari, OtariError


def _client(handler):
    o = Otari("http://otari.test", "sk-admin")
    o.http = httpx.Client(transport=httpx.MockTransport(handler))
    return o


def test_chat_reads_provider_and_model_headers():
    def handler(request):
        assert request.headers["authorization"] == "Bearer tk-team"
        assert request.url.path == "/api/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "[]"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 1}},
                              headers={"otari-provider": "ollama", "otari-model": "qwen2.5:3b", "otari-request-id": "r1"})

    res = _client(handler).chat("tk-team", "ollama:qwen2.5:3b", [], 10, 5)
    assert (res.provider, res.model, res.request_id, res.prompt_tokens) == ("ollama", "qwen2.5:3b", "r1", 3)


def test_chat_error_carries_status():
    o = _client(lambda r: httpx.Response(424, json={"detail": "no credential", "code": "provider_not_configured"}))
    with pytest.raises(OtariError) as e:
        o.chat("tk", "ollama:x", [], 10, 5)
    assert e.value.status == 424 and "424" in str(e.value)


def test_key_usage_swallows_gateway_failure():
    o = _client(lambda r: httpx.Response(500, text="boom"))
    assert o.key_usage("tk", "2026-01-01T00:00:00Z") == {}
