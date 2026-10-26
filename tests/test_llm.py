import httpx
import pytest

from ai_radar import llm

CFG = {"base_url": "https://x/v1", "model": "m1", "fallback_models": ["m2"], "api_key_env": "K"}


def _response(status, model=None, headers=None):
    body = {"choices": [{"message": {"content": f"from {model}"}}]} if status == 200 else {"error": "busy"}
    return httpx.Response(status, json=body, headers=headers or {})


def test_retries_then_falls_back_to_next_model(monkeypatch):
    monkeypatch.setenv("K", "secret")
    sleeps, calls = [], []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)

    def post(url, headers, json, timeout):
        calls.append(json["model"])
        return _response(200, "m2") if json["model"] == "m2" else _response(503, headers={"retry-after": "0"})

    monkeypatch.setattr(llm.httpx, "post", post)
    assert llm.chat(CFG, "s", "u", retries=2) == "from m2"
    assert calls == ["m1", "m1", "m1", "m2"]
    # A retry-after of 0 must not turn backoff into a busy loop.
    assert sleeps == [5.0, 10.0]


def test_reports_every_model_error(monkeypatch):
    monkeypatch.setenv("K", "secret")
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _response(404))
    with pytest.raises(llm.LLMError, match="m1: HTTP 404.*m2: HTTP 404"):
        llm.chat(CFG, "s", "u", retries=0)
