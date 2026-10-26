from __future__ import annotations

import calendar
import html
import re
from datetime import UTC, datetime

import feedparser

from ..models import Item
from .http import client

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str, limit: int = 500) -> str:
    text = html.unescape(_TAG_RE.sub(" ", text or ""))
    return " ".join(text.split())[:limit]


def _entry_time(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = entry.get(attr)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), UTC)
    return None


def parse_feed(text: str, name: str, tier: str, since: datetime) -> list[Item]:
    parsed = feedparser.parse(text)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"unparseable feed: {parsed.bozo_exception}")
    items = []
    for e in parsed.entries:
        published = _entry_time(e)
        # Undated entries can't be placed in the window; skip rather than resurface old posts.
        if not published or published < since or not e.get("link"):
            continue
        items.append(
            Item(
                title=_clean(e.get("title", ""), 300),
                url=e.link,
                source=name,
                kind="rss",
                tier=tier,
                published=published,
                summary=_clean(e.get("summary", "")),
            )
        )
    return items


def fetch(source: dict, since: datetime) -> list[Item]:
    with client() as c:
        resp = c.get(source["url"])
        resp.raise_for_status()
    return parse_feed(resp.text, source["name"], source.get("tier", "core"), since)
