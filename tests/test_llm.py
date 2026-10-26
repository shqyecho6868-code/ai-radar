from types import SimpleNamespace

import pytest

from ai_radar import llm

CFG = {"model": "claude-opus-5-5", "api_key_env": "K"}


class FakeStream:
    def __init__(self, msg, seen):
        self.msg, self.seen = msg, seen

    def __call__(self, **kwargs):
        self.seen.update(kwargs)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.msg


def _patch(monkeypatch, msg):
    seen = {}
    fake = FakeStream(msg, seen)

    class Client:
        def __init__(self, **kwargs):
            self.beta = SimpleNamespace(messages=SimpleNamespace(stream=fake))

    monkeypatch.setenv("K", "secret")
    monkeypatch.setattr(llm.anthropic, "Anthropic", Client)
    return seen


def _msg(stop_reason="end_turn", text="hi"):
    blocks = [SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(stop_reason=stop_reason, stop_details=None, content=blocks)


def test_returns_text_blocks_only(monkeypatch):
    seen = _patch(monkeypatch, _msg(text="brief"))
    assert llm.chat(CFG, "sys", "user") == "brief"
    assert seen["model"] == "claude-opus-5-5"
    assert seen["system"] == "sys"
    assert "temperature" not in seen


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_incomplete_output_raises(monkeypatch, reason):
    _patch(monkeypatch, _msg(stop_reason=reason))
    with pytest.raises(llm.LLMError):
        llm.chat(CFG, "s", "u")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("K", raising=False)
    with pytest.raises(llm.LLMError, match="missing env var K"):
        llm.chat(CFG, "s", "u")
