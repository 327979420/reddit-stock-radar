from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import AppSettings, load_config
from app.database import Database
from app.database.models import Stock, TickerMetric
from app.discord.formatter import format_radar
from app.jobs.service import RadarJobs
from app.logging import configure_logging
from app.ticker.master import seed_stocks
from app.ticker.reprocess import reprocess_mentions
from app.ticker.sec_master import update_from_sec


def setup():
    settings = AppSettings()
    configure_logging(settings.log_level)
    config = load_config(settings.radar_config)
    db = Database(settings.database_url)
    db.create_all()
    with db.session() as session:
        seed_stocks(session)
    return settings, config, db, RadarJobs(db, settings, config)


def main() -> None:
    parser = argparse.ArgumentParser(prog="radar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("update-stocks")
    sub.add_parser("reprocess")
    sub.add_parser("collect")
    score_parser = sub.add_parser("score")
    score_parser.add_argument(
        "--window", choices=["1h", "6h", "24h", "7d", "30d", "90d"], default="24h"
    )
    show = sub.add_parser("show")
    show.add_argument("--window", choices=["24h", "7d", "30d", "90d"], default="24h")
    show.add_argument("--limit", type=int, default=20)
    ticker = sub.add_parser("ticker")
    ticker.add_argument("symbol")
    publish = sub.add_parser("publish")
    publish.add_argument("--force", action="store_true")
    hot_posts = sub.add_parser("publish-hot-posts")
    hot_posts.add_argument("--force", action="store_true")
    sub.add_parser("run")
    args = parser.parse_args()
    _settings, config, db, jobs = setup()
    if args.command == "init-db":
        print("Database initialized and stock seed imported.")
    elif args.command == "update-stocks":
        with db.session() as session:
            count = update_from_sec(session, _settings.reddit_user_agent)
        print(f"Updated {count} Nasdaq/NYSE stocks from SEC.")
    elif args.command == "reprocess":
        with db.session() as session:
            stats = reprocess_mentions(session, config)
        print(f"Rebuilt {stats.mentions} mentions across {len(stats.tickers)} tickers.")
    elif args.command == "collect":
        asyncio.run(jobs.collect())
    elif args.command == "score":
        rows = jobs.score((args.window,))[args.window]
        print(format_radar(rows, datetime.now(ZoneInfo(config.timezone)), args.window, len(rows)))
    elif args.command == "show":
        rows = jobs.score((args.window,))[args.window]
        print(format_radar(rows, datetime.now(ZoneInfo(config.timezone)), args.window, args.limit))
    elif args.command == "publish":
        asyncio.run(jobs.publish(force=args.force))
    elif args.command == "publish-hot-posts":
        asyncio.run(jobs.publish_hot_posts(force=args.force))
    elif args.command == "run":
        from app.main import run

        asyncio.run(run())
    elif args.command == "ticker":
        with db.session() as session:
            stock = session.scalar(select(Stock).where(Stock.ticker == args.symbol.upper()))
            if not stock:
                raise SystemExit("Ticker not found in stock master.")
            print(f"{stock.ticker} — {stock.company_name}")
            for window in ("24h", "7d", "30d", "90d"):
                metric = session.scalar(
                    select(TickerMetric)
                    .where(TickerMetric.stock_id == stock.id, TickerMetric.window == window)
                    .order_by(TickerMetric.as_of.desc())
                    .limit(1)
                )
                if metric:
                    print(
                        f"{window}: #{metric.rank} | Heat {metric.heat_score:.0f} | Mentions {metric.mentions:,}"
                    )


if __name__ == "__main__":
    main()
