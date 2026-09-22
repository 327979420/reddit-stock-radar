from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import AppSettings, load_config
from app.database import Database
from app.jobs.service import RadarJobs
from app.logging import configure_logging
from app.ticker.master import seed_stocks


async def run() -> None:
    settings = AppSettings()
    configure_logging(settings.log_level)
    config = load_config(settings.radar_config)
    db = Database(settings.database_url)
    db.create_all()
    with db.session() as session:
        seed_stocks(session)
    jobs = RadarJobs(db, settings, config)
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(
        jobs.collect,
        "interval",
        minutes=config.poll_interval_minutes,
        id="reddit-collector",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        jobs.scheduled_score,
        "interval",
        hours=1,
        id="metric-scorer",
        max_instances=1,
        coalesce=True,
    )
    hour, minute = map(int, config.daily_publish_time.split(":"))
    scheduler.add_job(
        jobs.publish,
        CronTrigger(hour=hour, minute=minute, timezone=config.timezone),
        id="daily-discord",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=18 * 60 * 60,
    )
    summary_hour, summary_minute = map(int, config.hot_posts_summary.publish_time.split(":"))
    scheduler.add_job(
        jobs.publish_hot_posts,
        CronTrigger(
            hour=summary_hour,
            minute=summary_minute,
            timezone=config.timezone,
        ),
        id="hot-posts-summary",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=18 * 60 * 60,
    )
    scheduler.start()
    await jobs.collect()
    await jobs.scheduled_score()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
