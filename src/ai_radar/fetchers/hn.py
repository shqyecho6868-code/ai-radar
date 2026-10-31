from __future__ import annotations

import re
from datetime import UTC, datetime

from ..models import Item
from .http import client

API = "https://hn.algolia.com/api/v1/search"


def keyword_pattern(keywords: list[str]) -> re.Pattern:
    alts = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    return re.compile(rf"\b(?:{alts})\b", re.IGNORECASE)


def parse_hits(hits: list[dict], pattern: re.Pattern) -> list[Item]:
    items = []
    for h in hits:
        title = h.get("title") or ""
        if not pattern.search(title):
            continue
        discussion = f"https://news.ycombinator.com/item?id={h['objectID']}"
        items.append(
            Item(
                title=title,
                # Ask/Show HN posts have no external URL; the discussion is the content.
                url=h.get("url") or discussion,
                source="Hacker News",
                kind="hn",
                published=datetime.fromtimestamp(h["created_at_i"], UTC),
                signal=h.get("points") or 0,
                extra={"discussion": discussion, "comments": h.get("num_comments") or 0},
            )
        )
    return items


def fetch(cfg: dict, keywords: list[str], since: datetime) -> list[Item]:
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>{int(since.timestamp())},points>={cfg['min_points']}",
        "hitsPerPage": cfg["max_hits"],
    }
    with client() as c:
        resp = c.get(API, params=params)
        resp.raise_for_status()
    items = parse_hits(resp.json()["hits"], keyword_pattern(keywords))
    return sorted(items, key=lambda i: i.signal, reverse=True)
