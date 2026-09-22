from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.collectors.arctic_shift import ArcticShiftClient
from app.collectors.reddit import RedditClient
from app.collectors.service import CollectionService
from app.config import AppSettings, RadarConfig
from app.database.models import CollectionRun, DiscordPost, RedditPost
from app.database.session import Database
from app.discord.client import DiscordSender, DiscordWebhookSender
from app.discord.formatter import format_radar
from app.scoring.service import ScoringService
from app.summary.service import HotPostsSummarizer, build_hot_posts_embed, prepare_posts

logger = logging.getLogger(__name__)


class RadarJobs:
    def __init__(self, db: Database, settings: AppSettings, config: RadarConfig):
        self.db = db
        self.settings = settings
        self.config = config
        # Collection keeps a SQLite write transaction open while it fetches data.
        # Scheduled jobs share this lock so publishers never race that transaction.
        self._job_lock = asyncio.Lock()

    async def collect(self) -> None:
        async with self._job_lock:
            await self._collect()

    async def _collect(self) -> None:
        if self.config.data_source == "arctic_shift":
            client = ArcticShiftClient(self.settings.arctic_shift_base_url)
        else:
            if not self.settings.reddit_client_id or not self.settings.reddit_client_secret:
                raise RuntimeError(
                    "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are required for reddit_oauth"
                )
            client = RedditClient(
                self.settings.reddit_client_id,
                self.settings.reddit_client_secret,
                self.settings.reddit_user_agent,
            )
        try:
            with self.db.session() as session:
                stats = await CollectionService(client, self.config).collect(session)
                logger.info(
                    "collection_complete posts=%s comments=%s mentions=%s errors=%s",
                    stats.posts,
                    stats.comments,
                    stats.mentions,
                    stats.errors,
                )
                if stats.posts < self.config.data_quality.minimum_daily_posts:
                    logger.warning("data_quality_low_posts posts=%s", stats.posts)
                recent_average = session.scalar(
                    select(func.avg(CollectionRun.posts_processed)).where(
                        CollectionRun.status.in_(("completed", "partial")),
                        CollectionRun.finished_at.is_not(None),
                    )
                )
                if (
                    recent_average
                    and stats.posts
                    < float(recent_average) * self.config.data_quality.volume_drop_warning_ratio
                ):
                    logger.warning(
                        "data_quality_volume_drop posts=%s average=%.1f",
                        stats.posts,
                        recent_average,
                    )
        finally:
            await client.close()

    def score(self, windows: tuple[str, ...] = ("1h", "6h", "24h", "7d", "30d", "90d")):
        output = {}
        as_of = datetime.now(UTC).replace(microsecond=0)
        with self.db.session() as session:
            service = ScoringService(self.config.weights)
            for window in windows:
                output[window] = service.calculate(session, window, as_of)
        return output

    async def scheduled_score(self):
        async with self._job_lock:
            return self.score()

    async def publish(self, force: bool = False) -> bool:
        async with self._job_lock:
            return await self._publish(force)

    async def _publish(self, force: bool = False) -> bool:
        has_bot = bool(self.settings.discord_bot_token and self.settings.discord_channel_id)
        if not has_bot and not self.settings.discord_webhook_url:
            raise RuntimeError(
                "Set DISCORD_WEBHOOK_URL, or both DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID"
            )
        local_now = datetime.now(ZoneInfo(self.config.timezone))
        destination = str(self.settings.discord_channel_id) if has_bot else "webhook-daily-radar"
        with self.db.session() as session:
            exists = session.scalar(
                select(DiscordPost).where(
                    DiscordPost.channel_id == destination,
                    DiscordPost.report_date == local_now.date(),
                    DiscordPost.window == "24h",
                )
            )
            existing_id = exists.id if exists else None
            if exists and not force:
                logger.info("discord_daily_report_already_sent")
                return False
            rows = ScoringService(self.config.weights).calculate(session, "24h")
            content = format_radar(rows, local_now)
        if has_bot:
            message_id = await DiscordSender(self.settings.discord_bot_token).send(
                self.settings.discord_channel_id,
                content,  # type: ignore[arg-type]
            )
        else:
            message_id = await DiscordWebhookSender(self.settings.discord_webhook_url).send(content)
        with self.db.session() as session:
            record = session.get(DiscordPost, existing_id) if existing_id else None
            if record is None:
                record = DiscordPost(
                    channel_id=destination,
                    report_date=local_now.date(),
                    window="24h",
                )
                session.add(record)
            record.message_id = message_id
            record.sent_at = datetime.now(UTC)
        return True

    async def publish_hot_posts(self, force: bool = False) -> bool:
        async with self._job_lock:
            return await self._publish_hot_posts(force)

    async def _publish_hot_posts(self, force: bool = False) -> bool:
        summary_config = self.config.hot_posts_summary
        if not summary_config.enabled:
            return False
        if not self.settings.discord_webhook_url:
            raise RuntimeError("DISCORD_WEBHOOK_URL is required for hot-post summaries")
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for hot-post summaries")
        local_now = datetime.now(ZoneInfo(self.config.timezone))
        with self.db.session() as session:
            last_sent = session.scalar(
                select(func.max(DiscordPost.sent_at)).where(DiscordPost.window == "hot-posts")
            )
            if last_sent is not None and not force:
                elapsed = datetime.now(UTC) - last_sent.replace(tzinfo=UTC)
                if elapsed < timedelta(days=summary_config.interval_days):
                    logger.info("hot_posts_summary_not_due")
                    return False
            cutoff = datetime.now(UTC) - timedelta(hours=summary_config.lookback_hours)
            posts = session.scalars(
                select(RedditPost)
                .where(RedditPost.created_at >= cutoff)
                .order_by((RedditPost.score + RedditPost.num_comments * 2).desc())
                .limit(summary_config.post_count)
            ).all()
            if not posts:
                logger.warning("hot_posts_summary_skipped_no_posts")
                return False
            prepared = prepare_posts(list(posts), summary_config.max_post_chars)
        # Do not keep a database transaction open during external network calls.
        digest = await HotPostsSummarizer(
            self.settings.openai_api_key, self.settings.openai_summary_model
        ).summarize(prepared)
        embed = build_hot_posts_embed(digest, prepared)
        message_id = await DiscordWebhookSender(self.settings.discord_webhook_url).send_embed(embed)
        with self.db.session() as session:
            session.add(
                DiscordPost(
                    channel_id="webhook",
                    report_date=local_now.date(),
                    window="hot-posts",
                    message_id=message_id,
                )
            )
        return True
