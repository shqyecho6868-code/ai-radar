from __future__ import annotations

import os
import time

import httpx

LIMIT = 4096


def truncate(text: str, limit: int = LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def send(text: str, *, retries: int = 3) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Plain text: Markdown/HTML parse modes reject unescaped characters in model output.
    payload = {"chat_id": chat_id, "text": truncate(text), "disable_web_page_preview": True}
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                return
            error = f"HTTP {resp.status_code}: {resp.json().get('description', '')}"
        except httpx.HTTPError as exc:
            error = type(exc).__name__
        if attempt < retries:
            time.sleep(2**attempt)
    # Never include the URL: it contains the bot token.
    raise RuntimeError(f"Telegram send failed after {retries} attempts: {error}")
