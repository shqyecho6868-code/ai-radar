from __future__ import annotations

import os
from datetime import datetime

from ..models import Item
from .http import client

API = "https://api.github.com/search/repositories"


def parse_repos(rows: list[dict]) -> list[Item]:
    return [
        Item(
            title=f"{r['full_name']}: {r.get('description') or ''}".strip(": "),
            url=r["html_url"],
            source="GitHub new repos",
            kind="repo",
            published=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            summary=(r.get("description") or "")[:500],
            signal=r.get("stargazers_count", 0),
            extra={"topics": r.get("topics", []), "language": r.get("language")},
        )
        for r in rows
    ]


def fetch(cfg: dict, since: datetime) -> list[Item]:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    found: dict[str, Item] = {}
    with client(headers=headers) as c:
        # GitHub search has no OR across topic: qualifiers, so one query per topic.
        for topic in cfg["topics"]:
            q = f"topic:{topic} created:>{since.date().isoformat()} stars:>={cfg['min_stars']}"
            resp = c.get(API, params={"q": q, "sort": "stars", "order": "desc", "per_page": 20})
            resp.raise_for_status()
            for item in parse_repos(resp.json()["items"]):
                found[item.url] = item
    return sorted(found.values(), key=lambda i: i.signal, reverse=True)[: cfg["max_items"]]
