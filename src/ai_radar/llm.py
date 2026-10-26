"""Minimal chat-completion client for any OpenAI-compatible endpoint.

Default provider is the Gemini API's OpenAI-compatible endpoint (free tier).
Switching provider means changing `llm` in settings.yaml and the key's env var.
"""
from __future__ import annotations

import os
import time

import httpx

RETRY_STATUS = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


def chat(cfg: dict, system: str, user: str, *, retries: int = 4) -> str:
    key = os.environ.get(cfg["api_key_env"])
    if not key:
        raise LLMError(f"missing env var {cfg['api_key_env']}")
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": cfg.get("temperature", 0.4),
    }
    delay = 5.0
    for attempt in range(retries + 1):
        resp = httpx.post(
            cfg["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=300,
        )
        if resp.status_code in RETRY_STATUS and attempt < retries:
            # Free tiers rate-limit per minute; back off and retry.
            time.sleep(float(resp.headers.get("retry-after") or delay))
            delay *= 2
            continue
        if resp.status_code != 200:
            raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"]
    raise LLMError("unreachable")
