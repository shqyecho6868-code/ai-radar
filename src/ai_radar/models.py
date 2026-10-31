from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query params that only track the click, never change the page.
_TRACKING_PREFIXES = ("utm_", "ref", "source", "fbclid", "gclid", "mc_")


def normalize_url(url: str) -> str:
    """Canonical form used for dedup: https, lowercase host, no www, no tracking, no trailing slash."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING_PREFIXES)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(query), ""))


@dataclass
class Item:
    title: str
    url: str
    source: str
    kind: str  # rss | hn | paper | repo
    published: datetime
    summary: str = ""
    tier: str = "core"
    # Popularity signal from the source (HN points, HF upvotes, GitHub stars); 0 if none.
    signal: int = 0
    # Other sources that pointed at the same URL, e.g. "Hacker News (412 pts)".
    also_on: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return hashlib.sha1(normalize_url(self.url).encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.key
        d["published"] = self.published.isoformat()
        return d
