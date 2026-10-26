"""One weekly call to the Claude API (Anthropic SDK).

Settings live under `llm` in settings.yaml; the key comes from ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import os

import anthropic


class LLMError(RuntimeError):
    pass


def chat(cfg: dict, system: str, user: str) -> str:
    key_env = cfg.get("api_key_env", "ANTHROPIC_API_KEY")
    key = os.environ.get(key_env)
    if not key:
        raise LLMError(f"missing env var {key_env}")
    # The SDK retries connection errors, 429 and 5xx itself; max_retries caps that.
    client = anthropic.Anthropic(api_key=key, max_retries=cfg.get("max_retries", 2))
    try:
        # Streaming keeps a long generation from hitting the HTTP read timeout.
        with client.beta.messages.stream(
            model=cfg["model"],
            max_tokens=cfg.get("max_tokens", 32000),
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": cfg.get("effort", "high")},
            # If a safety classifier declines, the API reruns on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise LLMError(f"HTTP {exc.status_code}: {' '.join(str(exc.message).split())[:300]}") from exc
    except anthropic.APIError as exc:
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc
    if msg.stop_reason == "refusal":
        raise LLMError(f"refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise LLMError("output hit max_tokens")
    return "".join(b.text for b in msg.content if b.type == "text")
