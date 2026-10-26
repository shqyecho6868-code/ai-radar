"""AIHOT (https://aihot.news): curated AI news, about half from X accounts.

Anonymous read-only API, no key. It covers the X / long-tail role Grok used to
fill. Titles and summaries are in Chinese; `title_en` is used when present.
"""
from __future__ import annotations

from datetime import datetime

from ..models import Item
from .http import client

API = "https://aihot.news/api/v1/items"
# The public API rejects clients without a browser-style User-Agent.
BROWSER_UA = "Mozilla/5.0 (compatible; ai-radar/0.1; +https://github.com/shqyecho6868-code/ai-radar)"


def _time(row: dict) -> datetime:
    raw = row.get("publishedAt") or row["discoveredAt"]
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def parse_items(rows: list[dict]) -> list[Item]:
    items = []
    for r in rows:
        if not r.get("url"):
            continue
        items.append(
            Item(
                title=r.get("title_en") or r.get("title", ""),
                url=r["url"],
                source=f"AIHOT · {r.get('source', '')}".rstrip(" ·"),
                kind="aihot",
                tier="longtail",
                published=_time(r),
                summary=(r.get("summary") or "")[:500],
                signal=int(r.get("score") or 0),
                extra={"title_zh": r.get("title"), "category": r.get("category"), "permalink": r.get("permalink")},
            )
        )
    return items


def _page(body) -> tuple[list[dict], str | None]:
    if isinstance(body, list):
        return body, None
    rows = body.get("items") or body.get("data") or []
    return rows, body.get("nextCursor") or body.get("next_cursor")


def fetch(cfg: dict, since: datetime) -> list[Item]:
    rows: list[dict] = []
    cursor = None
    with client(headers={"User-Agent": BROWSER_UA}) as c:
        for _ in range(cfg["max_pages"]):
            params = {"mode": "selected", "window": "7d", "limit": 100}
            if cursor:
                params["cursor"] = cursor
            resp = c.get(API, params=params)
            resp.raise_for_status()
            page, cursor = _page(resp.json())
            rows += page
            if not cursor:
                break
    items = [i for i in parse_items(rows) if i.published >= since]
    return sorted(items, key=lambda i: i.signal, reverse=True)[: cfg["max_items"]]
