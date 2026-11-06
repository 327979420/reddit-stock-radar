# Reddit Stock Radar

**See where retail traders’ attention is concentrating.**

Reddit is noisy, but that noise can reveal which stocks and stories are drawing a crowd. Reddit Stock Radar turns discussions into a clearer view of popular tickers, changing attention, and recurring narratives for quick Discord briefings.

Built for my own research and my Discord group, it helps us decide what to read next without scrolling through every thread.

## A real snapshot

Top five by Heat Score from a saved 24-hour ranking, **16 August 2026, 20:28 UTC**. This is historical collected data, not a live market reading.

| Ticker | Heat / 100 | Mentions | Attention change |
| :--- | ---: | ---: | ---: |
| NVDA | 83.7 | 27 | +22.7% |
| RDDT | 74.3 | 43 | -43.4% |
| MU | 72.0 | 9 | +200.0% |
| BLSH | 70.4 | 11 | +37.5% |
| TSLA | 65.4 | 8 | +60.0% |

Attention change compares mentions with the preceding 24 hours. Heat combines mentions, unique authors, engagement, community coverage, and momentum, so the most-mentioned ticker is not always ranked first.

## What the briefing shows

- **Where attention sits:** ranked tickers, mention counts, and relative heat.
- **What is changing:** rising, falling, and newly appearing names, plus ranking changes and windows from 1 hour to 90 days.
- **What people are talking about:** Chinese summaries of popular posts, shared themes, and crowd sentiment, with links back to the discussions.

By default, Discord receives a daily Top 20 (the top three as headlines, the rest as a compact table) and a separate five-post digest every three days that skips recurring daily discussion threads. Themes come from the selected posts; there is no dedicated bullish/bearish sentiment score.

## How it works

**Collect discussions → identify tickers → measure attention changes → summarise popular conversations → deliver a briefing**

The collector follows eight investing communities through Arctic Shift, identifies tickers using a stock list and context filters, and saves attention rankings over time. Optional AI summaries add context to the numbers.

Use it as a starting point for research and group discussion. Attention does not predict price movement, and a high Heat Score is not a buy signal.

Arctic Shift is an unofficial archive with possible delays and gaps. Coverage depends on collected discussions and the stock list; history builds from collection rather than arriving as a complete 90-day backfill.

## Run locally

Python 3.12+, SQLite or PostgreSQL, with Discord delivery and optional OpenAI summaries.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
radar init-db
radar collect
radar show --window 24h --limit 20
```

Configure communities and schedules in `app/config/default.yaml`. The default Arctic Shift source needs no Reddit credentials. Local rankings need no Discord or OpenAI credentials.

For delivery, set `DISCORD_WEBHOOK_URL` in `.env`; hot-post summaries also need `OPENAI_API_KEY`. Run `radar run` to enable collection and scheduled delivery. Keep `.env` private. Queries currently use the CLI, not Discord slash commands.

Checks: `pytest -q` and `ruff check app tests scripts`.
