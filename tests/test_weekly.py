from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from ai_radar.collect import SourceResult
from ai_radar.deliver.telegram import truncate
from ai_radar.models import Item
from ai_radar.weekly import (
    drop_used,
    is_month_end,
    parse_reply,
    pop_requested_topic,
    render,
    section,
    should_publish,
    week_label,
)

LA = ZoneInfo("America/Los_Angeles")


def _item(url, title="T"):
    return Item(title=title, url=url, source="S", kind="rss", published=datetime(2026, 10, 24, tzinfo=UTC))


@pytest.mark.parametrize(
    "utc_hour, expected",
    [
        # PDT (UTC-7): the 15:17 UTC run is 08:17 local and publishes.
        ((2026, 10, 25, 15, 17), True),
        # PST (UTC-8): the 15:17 UTC run is 07:17 local and waits for the 16:17 run.
        ((2026, 11, 8, 15, 17), False),
        ((2026, 11, 8, 16, 17), True),
    ],
)
def test_publish_hour_across_daylight_saving(utc_hour, expected):
    local = datetime(*utc_hour, tzinfo=UTC).astimezone(LA)
    assert should_publish(local, 8, already_published=False, force=False) is expected


def test_already_published_skips_unless_forced():
    local = datetime(2026, 10, 25, 9, tzinfo=LA)
    assert not should_publish(local, 8, already_published=True, force=False)
    assert should_publish(local, 8, already_published=True, force=True)


def test_week_label_uses_iso_week():
    assert week_label(datetime(2026, 10, 25, 8, tzinfo=LA)) == "2026-W43"
    assert week_label(datetime(2027, 1, 3, 8, tzinfo=LA)) == "2026-W53"


def test_month_end_is_last_sunday_of_month():
    assert is_month_end(datetime(2026, 10, 25, tzinfo=LA))
    assert not is_month_end(datetime(2026, 10, 18, tzinfo=LA))


def test_pop_requested_topic_takes_first_entry_only():
    text = "# Topic queue\n\nintro\n- KV cache\n- Raft\n"
    topic, rest = pop_requested_topic(text)
    assert topic == "KV cache"
    assert rest == "# Topic queue\n\nintro\n- Raft\n"
    assert pop_requested_topic("# empty\n") == (None, "# empty\n")


def test_parse_reply_drops_unknown_ids_and_requires_a_source():
    a = _item("https://a.com")
    by_id = {a.key: a}
    reply = f'<!-- meta: {{"topic_en": "X", "source_ids": ["{a.key}", "bogus"], "also_ids": ["nope"]}} -->\n## What & Why\nbody'
    meta, body = parse_reply(reply, by_id)
    assert meta["source_ids"] == [a.key]
    assert meta["also_ids"] == []
    assert body.startswith("## What & Why")
    with pytest.raises(ValueError):
        parse_reply('<!-- meta: {"topic_en": "X", "source_ids": ["bogus"]} -->', by_id)
    with pytest.raises(ValueError):
        parse_reply("## no meta", by_id)


def test_render_links_sources_and_lists_failed_sources():
    a, b = _item("https://a.com", "Alpha"), _item("https://b.com", "Beta")
    by_id = {a.key: a, b.key: b}
    meta = {"topic_en": "Topic", "topic_zh": "主题", "difficulty": "中等", "durability": 4,
            "source_ids": [a.key], "also_ids": [b.key]}
    out = render("2026-W44", meta, "## What & Why\nx", by_id, [SourceResult("HN", False, 0, 0, "e"), SourceResult("R", True, 3, 0)])
    assert out.startswith("# AI Radar · 2026-W44 · Topic")
    assert "1. **Source 1**: [Alpha](https://a.com) · S" in out
    assert "1. **Also 1**: [Beta](https://b.com) · S" in out
    assert "_1/2 sources ok; failed: HN_" in out


def test_section_extracts_until_next_heading():
    body = "## 上周回顾\nlast\n\n## What & Why\nwhy text\n\n## Demo\nsteps"
    assert section(body, "What & Why") == "why text"
    assert section(body, "Missing") == ""


def test_drop_used_skips_urls_from_past_weeks():
    state = {"weeks": [{"week": "2026-W43", "topic": "t", "source_urls": ["https://www.a.com/"]}]}
    assert [i.url for i in drop_used([_item("https://a.com"), _item("https://b.com")], state)] == ["https://b.com"]


def test_truncate_respects_telegram_limit():
    assert len(truncate("x" * 5000)) == 4096
    assert truncate("short") == "short"
