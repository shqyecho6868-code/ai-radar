from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import Item
from .http import client

API = "https://huggingface.co/api/daily_papers"


def parse_papers(rows: list[dict], min_upvotes: int) -> list[Item]:
    items = []
    for row in rows:
        paper = row.get("paper", {})
        upvotes = paper.get("upvotes", 0)
        if upvotes < min_upvotes:
            continue
        arxiv_id = paper["id"]
        items.append(
            Item(
                title=row.get("title") or paper.get("title", ""),
                url=f"https://huggingface.co/papers/{arxiv_id}",
                source="Hugging Face Papers",
                kind="paper",
                published=datetime.fromisoformat(row["publishedAt"].replace("Z", "+00:00")),
                summary=(paper.get("ai_summary") or paper.get("summary") or "")[:500],
                signal=upvotes,
                extra={"arxiv": f"https://arxiv.org/abs/{arxiv_id}", "github": paper.get("githubRepo")},
            )
        )
    return items


def fetch(cfg: dict, since: datetime) -> list[Item]:
    items: list[Item] = []
    day = since.date()
    today = datetime.now(UTC).date()
    with client() as c:
        while day <= today:
            resp = c.get(API, params={"date": day.isoformat()})
            resp.raise_for_status()
            items += parse_papers(resp.json(), cfg["min_upvotes"])
            day += timedelta(days=1)
    # A paper can be featured on more than one day.
    unique = {i.url: i for i in items}
    return sorted(unique.values(), key=lambda i: i.signal, reverse=True)[: cfg["max_items"]]
