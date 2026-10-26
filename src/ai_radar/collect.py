"""Collect this week's candidates from every configured source.

Usage: python -m ai_radar.collect [--out out/]

Each source runs in isolation: one failing source is recorded in the report and
never stops the others.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

import yaml

from .fetchers import github_repos, hf_papers, hn, rss
from .models import Item, normalize_url

CONFIG = Path(__file__).resolve().parents[2] / "config"


@dataclass
class SourceResult:
    name: str
    ok: bool
    count: int
    seconds: float
    error: str = ""


def load_config(config_dir: Path = CONFIG) -> dict:
    return {f: yaml.safe_load((config_dir / f"{f}.yaml").read_text()) for f in ("settings", "sources", "interests")}


def dedup(items: list[Item]) -> list[Item]:
    """Keep the first item per normalized URL; later duplicates are recorded in also_on."""
    seen: dict[str, Item] = {}
    for item in items:
        key = normalize_url(item.url)
        if key not in seen:
            seen[key] = item
            continue
        label = f"{item.source} ({item.signal})" if item.signal else item.source
        seen[key].also_on.append(label)
        seen[key].signal = max(seen[key].signal, item.signal)
    return list(seen.values())


def _run(name: str, fn: Callable[[], list[Item]], cap: int) -> tuple[list[Item], SourceResult]:
    start = time.monotonic()
    try:
        items = fn()[:cap]
        return items, SourceResult(name, True, len(items), time.monotonic() - start)
    except Exception as exc:  # noqa: BLE001 - isolate any source failure
        return [], SourceResult(name, False, 0, time.monotonic() - start, " ".join(f"{type(exc).__name__}: {exc}".split())[:200])


def collect(cfg: dict, now: datetime | None = None) -> tuple[list[Item], list[SourceResult]]:
    settings = cfg["settings"]
    since = (now or datetime.now(UTC)) - timedelta(days=settings["lookback_days"])
    cap = settings["max_items_per_source"]

    jobs: list[tuple[str, Callable[[], list[Item]]]] = [
        (s["name"], lambda s=s: rss.fetch(s, since)) for s in cfg["sources"]["rss"]
    ]
    jobs += [
        ("Hacker News", lambda: hn.fetch(settings["hn"], cfg["interests"]["hn_keywords"], since)),
        ("Hugging Face Papers", lambda: hf_papers.fetch(settings["hf_papers"], since)),
        ("GitHub new repos", lambda: github_repos.fetch(settings["github_repos"], since)),
    ]

    items: list[Item] = []
    results: list[SourceResult] = []
    for name, fn in jobs:
        got, result = _run(name, fn, cap)
        items += got
        results.append(result)
    return dedup(items), results


def render_report(items: list[Item], results: list[SourceResult]) -> str:
    lines = ["# Candidate pool", "", f"{len(items)} candidates from {sum(r.ok for r in results)}/{len(results)} sources.", ""]
    lines += ["| Source | Status | Items | Seconds |", "| --- | --- | --- | --- |"]
    for r in results:
        status = "ok" if r.ok else f"FAILED: {r.error}"
        lines.append(f"| {r.name} | {status} | {r.count} | {r.seconds:.1f} |")
    lines += ["", "## Items", ""]
    for i in sorted(items, key=lambda i: i.published, reverse=True):
        extra = f" · {i.signal}" if i.signal else ""
        also = f" · also on {', '.join(i.also_on)}" if i.also_on else ""
        lines.append(f"- {i.published:%m-%d} [{i.source}{extra}{also}] [{i.title}]({i.url})")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    items, results = collect(load_config())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "candidates.json").write_text(json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2))
    report = render_report(items, results)
    (args.out / "report.md").write_text(report)
    print(report)
    # Fail only if every source failed; partial failures are reported, not fatal.
    return 0 if any(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
