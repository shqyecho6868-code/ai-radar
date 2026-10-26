from datetime import UTC, datetime, timedelta

from ai_radar.collect import SourceResult, dedup, render_report
from ai_radar.fetchers import github_repos, hf_papers, hn, rss
from ai_radar.models import Item, normalize_url

NOW = datetime(2026, 10, 26, 15, 0, tzinfo=UTC)


def _item(url, source="A", signal=0):
    return Item(title="t", url=url, source=source, kind="rss", published=NOW, signal=signal)


def test_normalize_url_strips_tracking_www_and_trailing_slash():
    assert normalize_url("http://www.Example.com/post/?utm_source=x&id=3") == "https://example.com/post?id=3"
    assert normalize_url("https://example.com") == "https://example.com/"


def test_dedup_keeps_first_and_records_other_sources():
    items = dedup([_item("https://a.com/x"), _item("https://www.a.com/x/?utm_medium=rss", "Hacker News", 412)])
    assert len(items) == 1
    assert items[0].source == "A"
    assert items[0].also_on == ["Hacker News (412)"]
    assert items[0].signal == 412


FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>f</title>
<item><title>New &amp; recent</title><link>https://b.com/new</link><pubDate>Sat, 24 Oct 2026 10:00:00 +0000</pubDate>
<description>&lt;p&gt;Hello   &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description></item>
<item><title>Too old</title><link>https://b.com/old</link><pubDate>Mon, 05 Oct 2026 10:00:00 +0000</pubDate></item>
<item><title>Undated</title><link>https://b.com/undated</link></item>
</channel></rss>"""


def test_parse_feed_filters_window_and_cleans_html():
    items = rss.parse_feed(FEED, "Blog", "core", NOW - timedelta(days=8))
    assert [i.url for i in items] == ["https://b.com/new"]
    assert items[0].title == "New & recent"
    assert items[0].summary == "Hello world"


def test_hn_keyword_filter_uses_word_boundaries():
    pattern = hn.keyword_pattern(["ai", "context engineering"])
    hits = [
        {"objectID": "1", "title": "Context Engineering for agents", "url": "https://c.com", "created_at_i": 1761400000, "points": 300},
        {"objectID": "2", "title": "Repairing a chair", "url": "https://d.com", "created_at_i": 1761400000, "points": 500},
        {"objectID": "3", "title": "Ask HN: Is AI hype?", "url": None, "created_at_i": 1761400000, "points": 200},
    ]
    items = hn.parse_hits(hits, pattern)
    assert [i.title for i in items] == ["Context Engineering for agents", "Ask HN: Is AI hype?"]
    assert items[1].url == "https://news.ycombinator.com/item?id=3"


def test_hf_papers_applies_upvote_threshold():
    rows = [
        {"title": "Big", "publishedAt": "2026-10-24T00:00:00.000Z", "paper": {"id": "2610.1", "upvotes": 80, "ai_summary": "s"}},
        {"title": "Small", "publishedAt": "2026-10-24T00:00:00.000Z", "paper": {"id": "2610.2", "upvotes": 3}},
    ]
    items = hf_papers.parse_papers(rows, min_upvotes=20)
    assert [i.title for i in items] == ["Big"]
    assert items[0].extra["arxiv"] == "https://arxiv.org/abs/2610.1"


def test_github_repo_title_without_description():
    rows = [{"full_name": "o/r", "description": None, "html_url": "https://github.com/o/r", "created_at": "2026-10-20T00:00:00Z", "stargazers_count": 900}]
    assert github_repos.parse_repos(rows)[0].title == "o/r"


def test_report_lists_failures_on_one_line():
    report = render_report([_item("https://a.com")], [SourceResult("X", False, 0, 0.1, "boom"), SourceResult("Y", True, 1, 0.2)])
    assert "| X | FAILED: boom | 0 | 0.1 |" in report
    assert "1/2 sources" in report


def test_aihot_prefers_english_title_and_falls_back_to_discovered_time():
    from ai_radar.fetchers import aihot

    rows = [
        {"title": "标题", "title_en": "Title", "url": "https://x.com/a/status/1", "source": "X：A (@a)", "publishedAt": None,
         "discoveredAt": "2026-10-24T10:00:00Z", "summary": "摘要", "category": "tip", "score": 82},
        {"title": "无链接", "url": None, "discoveredAt": "2026-10-24T10:00:00Z"},
    ]
    items = aihot.parse_items(rows)
    assert len(items) == 1
    assert items[0].title == "Title"
    assert items[0].published.isoformat() == "2026-10-24T10:00:00+00:00"
    assert items[0].extra["title_zh"] == "标题"
    assert aihot._page({"items": rows, "nextCursor": "c2"})[1] == "c2"
