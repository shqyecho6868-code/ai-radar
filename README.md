# AI Radar

The fetch half of a weekly AI learning loop. Every Sunday a GitHub Action collects the past
week's posts from AI labs, practitioners, Hacker News, Hugging Face Papers, new GitHub repos
and AIHOT (which covers long-form posts on X), dedups them and commits the pool to
`pool/<ISO week>/`. No LLM call, no cost.

The study doc itself is written in a Claude project: it reads that week's pool, the learner's
progress and feedback, and picks the next step of a progressive curriculum. The pool keeps it
current; it is not a news digest.

An earlier fully automated version (Claude API writes the brief, Telegram delivery) is kept on
the `m2-weekly` branch.

## Run locally

```bash
pip install -e ".[dev]"
pytest
python -m ai_radar.collect --out out   # writes out/candidates.json and out/report.md
```

Sources live in `config/sources.yaml`; thresholds in `config/settings.yaml`. Changing
either needs no code change.

Output: `pool/<week>/candidates.json` (the pool) and `pool/<week>/report.md` (per-source status).
