# AI Radar

A weekly AI learning brief. Every Sunday it collects the past week's posts from AI labs,
practitioners, Hacker News, Hugging Face Papers and new GitHub repos, picks **one** durable
topic worth a week of study, and pushes it to Telegram with sources, prerequisites, a demo
idea and a blog skeleton.

Runs entirely on GitHub Actions and GitHub Models (free for public repos).

## Status

- [x] M1: collection from all sources (`python -m ai_radar.collect`)
- [ ] M2: weekly pick with one strong-model call, Telegram delivery, Markdown archive
- [ ] M3: Sunday schedule and failure notice

## Run locally

```bash
pip install -e ".[dev]"
pytest
python -m ai_radar.collect --out out   # writes out/candidates.json and out/report.md
```

Sources live in `config/sources.yaml`; thresholds in `config/settings.yaml`. Changing
either needs no code change.
