"""Weekly brief: collect, let the LLM pick one topic, archive it and push to Telegram.

Usage: python -m ai_radar.weekly [--force] [--dry-run]

--force    ignore the publish-hour and already-published checks
--dry-run  write to out/ only; no Telegram, no archive or state changes
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import llm
from .collect import SourceResult, collect, load_config
from .deliver import telegram
from .models import Item, normalize_url

ROOT = Path(__file__).resolve().parents[2]
META_RE = re.compile(r"\A\s*<!--\s*meta:\s*(\{.*?\})\s*-->\s*", re.DOTALL)


def week_label(local: datetime) -> str:
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


def should_publish(local: datetime, publish_hour: int, already_published: bool, force: bool) -> bool:
    if force:
        return True
    return not already_published and local.hour >= publish_hour


def is_month_end(local: datetime) -> bool:
    """True on the month's last weekly run: next week's run falls in another month."""
    return local.day + 7 > calendar.monthrange(local.year, local.month)[1]


def pop_requested_topic(text: str) -> tuple[str | None, str]:
    """Return the first `- ` line of topic-queue.md and the file without it."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("- ") and line[2:].strip():
            return line[2:].strip(), "".join(lines[:i] + lines[i + 1 :])
    return None, text


def classics(path: Path, now: datetime) -> list[Item]:
    rows = yaml.safe_load(path.read_text()) or []
    return [
        Item(title=r["title"], url=r["url"], source=r["source"], kind="classic", tier="classic", published=now)
        for r in rows
    ]


def drop_used(items: list[Item], state: dict) -> list[Item]:
    used = {normalize_url(u) for w in state["weeks"] for u in w.get("source_urls", [])}
    return [i for i in items if normalize_url(i.url) not in used]


def candidate_lines(items: list[Item]) -> str:
    lines = []
    for i in items:
        meta = " · ".join(x for x in (i.source, f"{i.published:%m-%d}", str(i.signal) if i.signal else "", i.tier) if x)
        summary = f" — {i.summary[:200]}" if i.summary else ""
        lines.append(f"[{i.key}] ({meta}) {i.title}{summary}")
    return "\n".join(lines)


def build_prompt(items: list[Item], state: dict, log: str, requested: str | None, month_end: bool) -> str:
    past = "\n".join(f"- {w['week']}: {w['topic']}" for w in state["weeks"][-12:]) or "(none yet)"
    return "\n\n".join(
        [
            f"## Requested topic\n{requested or ''}",
            f"## Past topics\n{past}",
            f"## Learning log\n{log.strip()}",
            f"## Month end\n{'yes' if month_end else 'no'}",
            f"## Candidates ({len(items)})\n{candidate_lines(items)}",
        ]
    )


def parse_reply(reply: str, by_id: dict[str, Item]) -> tuple[dict, str]:
    m = META_RE.match(reply)
    if not m:
        raise ValueError("LLM reply has no meta comment on line 1")
    meta = json.loads(m.group(1))
    meta["source_ids"] = [i for i in meta.get("source_ids", []) if i in by_id]
    meta["also_ids"] = [i for i in meta.get("also_ids", []) if i in by_id]
    if not meta["source_ids"]:
        raise ValueError("LLM reply cites no known candidate ids")
    return meta, reply[m.end() :].strip()


def render(week: str, meta: dict, body: str, by_id: dict[str, Item], results: list[SourceResult]) -> str:
    def link(n: int, prefix: str, item: Item) -> str:
        return f"{n}. **{prefix} {n}**: [{item.title}]({item.url}) · {item.source}"

    sources = [link(n, "Source", by_id[i]) for n, i in enumerate(meta["source_ids"], 1)]
    also = [link(n, "Also", by_id[i]) for n, i in enumerate(meta["also_ids"], 1)]
    failed = [r.name for r in results if not r.ok]
    parts = [
        f"# AI Radar · {week} · {meta['topic_en']}",
        f"{meta.get('topic_zh', '')} · 难度：{meta.get('difficulty', '?')} · 耐久度 {'★' * int(meta.get('durability', 0))}",
        body,
        "## Sources\n\n" + "\n".join(sources),
    ]
    if also:
        parts.append("## Also\n\n" + "\n".join(also))
    footer = f"_{len(results) - len(failed)}/{len(results)} sources ok"
    parts.append(footer + (f"; failed: {', '.join(failed)}_" if failed else "_"))
    return "\n\n".join(parts) + "\n"


def section(body: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", body, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def telegram_text(week: str, meta: dict, body: str, by_id: dict[str, Item], archive_url: str) -> str:
    sources = "\n".join(f"{n}. {by_id[i].title}\n{by_id[i].url}" for n, i in enumerate(meta["source_ids"], 1))
    return "\n\n".join(
        x
        for x in [
            f"🛰 AI Radar · {week}\n{meta['topic_en']} · {meta.get('topic_zh', '')}",
            section(body, "上周回顾"),
            section(body, "What & Why"),
            f"Sources\n{sources}",
            f"完整学习计划（demo、博客骨架）：\n{archive_url}",
        ]
        if x
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config()
    settings = cfg["settings"]
    now = datetime.now(UTC)
    local = now.astimezone(ZoneInfo(settings["timezone"]))
    week = week_label(local)
    archive = ROOT / "weekly" / f"{week}.md"

    if not should_publish(local, settings["publish_hour"], archive.exists(), args.force):
        print(f"skip: {week} local {local:%H:%M}, published={archive.exists()}")
        return 0

    state_path = ROOT / "data" / "state.json"
    queue_path = ROOT / "topic-queue.md"
    state = json.loads(state_path.read_text())
    requested, queue_rest = pop_requested_topic(queue_path.read_text())

    items, results = collect(cfg, now)
    items = drop_used(items + classics(ROOT / "config" / "classics.yaml", now), state)
    by_id = {i.key: i for i in items}

    system = (ROOT / "prompts" / "weekly.md").read_text()
    user = build_prompt(items, state, (ROOT / "learning-log.md").read_text(), requested, is_month_end(local))
    meta, body = parse_reply(llm.chat(settings["llm"], system, user), by_id)
    brief = render(week, meta, body, by_id, results)

    repo = os.environ.get("GITHUB_REPOSITORY", "shqyecho6868-code/ai-radar")
    archive_url = f"https://github.com/{repo}/blob/main/weekly/{week}.md"
    message = telegram_text(week, meta, body, by_id, archive_url)

    if args.dry_run:
        out = ROOT / "out"
        out.mkdir(exist_ok=True)
        (out / f"{week}.md").write_text(brief)
        (out / "telegram.txt").write_text(message)
        print(brief)
        return 0

    archive.parent.mkdir(exist_ok=True)
    archive.write_text(brief)
    state["weeks"].append(
        {"week": week, "topic": meta["topic_en"], "source_urls": [by_id[i].url for i in meta["source_ids"]]}
    )
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    if requested:
        queue_path.write_text(queue_rest)
    telegram.send(message)
    print(f"published {week}: {meta['topic_en']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
