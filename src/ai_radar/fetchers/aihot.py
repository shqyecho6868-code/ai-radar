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


def _first_url(value) -> str | None:
    if isinstance(value, str):
        return value if value.startswith("http") else None
    if isinstance(value, dict):
        # Prefer the original article over AIHOT's own reading page.
        for key in ("original", "source", "canonical", "url", "href"):
            if url := _first_url(value.get(key)):
                return url
        return next((u for v in value.values() if (u := _first_url(v))), None)
    if isinstance(value, list):
        return next((u for v in value if (u := _first_url(v))), None)
    return None


def _url(row: dict) -> str | None:
    """v1 rows carry links in `links`; legacy rows had a top-level `url`."""
    return _first_url(row.get("url")) or _first_url(row.get("links")) or _first_url(row.get("attribution"))


def parse_items(rows: list[dict]) -> list[Item]:
    items = []
    for r in rows:
        url = _url(r)
        if not url:
            continue
        summary = " ".join(x for x in (r.get("summary"), r.get("reason")) if x)
        items.append(
            Item(
                # originalTitle is the source-language title (often English); title is AIHOT's Chinese one.
                title=r.get("originalTitle") or r.get("title_en") or r.get("title", ""),
                url=url,
                source=f"AIHOT · {r.get('source', '')}".rstrip(" ·"),
                kind="aihot",
                tier="longtail",
                published=_time(r),
                summary=summary[:500],
                signal=int(r.get("score") or 0),
                extra={"title_zh": r.get("title"), "category": r.get("category"), "permalink": r.get("permalink")},
            )
        )
    return items


def _page(body) -> tuple[list[dict], str | None]:
    if isinstance(body, list):
        return body, None
    rows = body.get("items") or body.get("data") or []
    if isinstance(rows, dict):  # {"data": {"items": [...], "nextCursor": ...}}
        return _page(rows)
    if not rows and body:
        # An unexpected shape would otherwise look like an empty week.
        raise ValueError(f"unrecognized AIHOT response, keys: {sorted(body)[:10]}")
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
    items = parse_items(rows)
    if rows and not items:
        raise ValueError(f"AIHOT rows have no recognizable link, sample links: {rows[0].get('links')!r}"[:180])
    items = [i for i in items if i.published >= since]
    return sorted(items, key=lambda i: i.signal, reverse=True)[: cfg["max_items"]]
