# AI Radar

A weekly AI learning brief. Every Sunday at 08:00 Seattle time it collects the past week's
posts from AI labs, practitioners, AIHOT (curated, about half from X), Hacker News, Hugging
Face Papers and new GitHub repos, picks **one** durable topic worth a week of study, and
pushes it to Telegram. The full plan (sources, prerequisites, a 1-hour and a 2-3 hour demo,
a blog skeleton, self-check questions) is archived in [`weekly/`](weekly/).

Runs on GitHub Actions with the Gemini API free tier: no server, no cost.

## How it works

```
collect (22 sources, isolated) -> dedup + drop past sources -> + classics fallback
  -> one LLM call picks the topic and writes the plan -> archive + state commit -> Telegram
```

The model only chooses candidate ids; links are rendered by the program, so they can't be
invented.

## Setup

1. **Gemini key**: create one at [Google AI Studio](https://aistudio.google.com/apikey).
2. **Telegram bot**: message [@BotFather](https://t.me/BotFather), send `/newbot`, keep the
   token. Send any message to your new bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy `chat.id`.
3. In the repo: Settings -> Secrets and variables -> Actions -> New repository secret:
   `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Actions -> weekly -> Run workflow (dry run is on by default) to check the output.

## Steering it

| File | Use |
| --- | --- |
| `topic-queue.md` | Add `- some topic` to choose next Sunday's topic. |
| `learning-log.md` | Optional log; scores steer future picks, the brief opens with last week's check-in. |
| `config/sources.yaml` | Add or remove feeds. |
| `config/classics.yaml` | Durable fallback reading for weak weeks. |
| `config/settings.yaml` | Thresholds, publish hour, model. |
| `prompts/weekly.md` | Selection rules and output format. |

## Run locally

```bash
pip install -e ".[dev]"
pytest
python -m ai_radar.collect --out out          # candidate pool + per-source report
GEMINI_API_KEY=... python -m ai_radar.weekly --dry-run --force   # writes out/<week>.md
```
