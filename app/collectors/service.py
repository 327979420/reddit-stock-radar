from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collectors.base import RedditDataClient
from app.config.settings import RadarConfig
from app.database.models import CollectionRun, RedditComment, RedditPost, Stock, TickerMention
from app.ticker.extractor import TickerExtractor

logger = logging.getLogger(__name__)


def author_hash(author: str | None) -> str | None:
    if not author or author == "[deleted]":
        return None
    return hashlib.sha256(author.encode()).hexdigest()


def from_timestamp(value: float) -> datetime:
    return datetime.fromtimestamp(value, UTC)


@dataclass
class CollectionStats:
    posts: int = 0
    comments: int = 0
    mentions: int = 0
    tickers: set[str] | None = None
    errors: int = 0
    filtered: int = 0

    def __post_init__(self) -> None:
        self.tickers = set()


class CollectionService:
    def __init__(self, client: RedditDataClient, config: RadarConfig):
        self.client = client
        self.config = config

    async def collect(self, session: Session) -> CollectionStats:
        run = CollectionRun()
        session.add(run)
        session.flush()
        session.commit()
        stats = CollectionStats()
        extractor = TickerExtractor(session, self.config)
        stock_ids = dict(session.execute(select(Stock.ticker, Stock.id)).all())
        try:
            for subreddit in self.config.subreddits:
                try:
                    await self._collect_subreddit(session, extractor, stock_ids, subreddit, stats)
                    session.commit()  # checkpoint each subreddit for crash recovery
                except Exception:
                    stats.errors += 1
                    session.rollback()
                    logger.exception("subreddit_collection_failed subreddit=%s", subreddit)
            run = session.get(CollectionRun, run.id)
            run.status = "completed" if not stats.errors else "partial"
        except Exception:
            run = session.get(CollectionRun, run.id)
            run.status = "failed"
            raise
        finally:
            run.finished_at = datetime.now(UTC)
            run.posts_processed = stats.posts
            run.comments_processed = stats.comments
            run.ticker_mentions_detected = stats.mentions
            run.unique_tickers = len(stats.tickers or set())
            run.api_errors = stats.errors
            run.false_positive_filtered = stats.filtered
        return stats

    async def _collect_subreddit(
        self,
        session: Session,
        extractor: TickerExtractor,
        stock_ids: dict[str, int],
        subreddit: str,
        stats: CollectionStats,
    ) -> None:
        comment_candidates: list[RedditPost] = []
        async for raw in self.client.new_posts(subreddit, self.config.posts_per_subreddit):
            post = session.scalar(select(RedditPost).where(RedditPost.reddit_id == raw["id"]))
            is_new = post is None
            if post is None:
                post = RedditPost(
                    reddit_id=raw["id"],
                    subreddit=raw.get("subreddit", subreddit),
                    author_hash=author_hash(raw.get("author")),
                    created_at=from_timestamp(raw["created_utc"]),
                    title=raw.get("title", ""),
                    selftext=raw.get("selftext", "")[:20000],
                    score=raw.get("score", 0),
                    upvote_ratio=raw.get("upvote_ratio"),
                    num_comments=raw.get("num_comments", 0),
                    permalink=raw.get("permalink", ""),
                )
                session.add(post)
                session.flush()
                stats.posts += 1
            else:
                post.score = raw.get("score", post.score)
                post.num_comments = raw.get("num_comments", post.num_comments)
                post.upvote_ratio = raw.get("upvote_ratio", post.upvote_ratio)
            if is_new and post.score >= self.config.minimum_post_score:
                result = extractor.extract(f"{post.title}\n{post.selftext}", subreddit)
                stats.filtered += result.filtered_count
                self._save_mentions(
                    session,
                    result.matches,
                    stock_ids,
                    "post",
                    post.reddit_id,
                    post.reddit_id,
                    post.author_hash,
                    post.subreddit,
                    post.created_at,
                    post.score,
                    stats,
                )
            if post.score >= self.config.minimum_post_score and post.num_comments > 0:
                comment_candidates.append(post)

        comment_candidates.sort(key=lambda post: post.score + post.num_comments, reverse=True)
        for post in comment_candidates[: self.config.hot_posts_for_comments]:
            for raw in await self.client.comments(
                subreddit, post.reddit_id, self.config.comments_per_post
            ):
                if raw.get("score", 0) < self.config.minimum_comment_score:
                    continue
                exists = session.scalar(
                    select(RedditComment.id).where(RedditComment.reddit_id == raw["id"])
                )
                if exists:
                    continue
                comment = RedditComment(
                    reddit_id=raw["id"],
                    post_id=post.id,
                    author_hash=author_hash(raw.get("author")),
                    created_at=from_timestamp(raw["created_utc"]),
                    body=raw.get("body", "")[:10000],
                    score=raw.get("score", 0),
                )
                session.add(comment)
                session.flush()
                stats.comments += 1
                result = extractor.extract(comment.body, subreddit)
                stats.filtered += result.filtered_count
                self._save_mentions(
                    session,
                    result.matches,
                    stock_ids,
                    "comment",
                    comment.reddit_id,
                    post.reddit_id,
                    comment.author_hash,
                    post.subreddit,
                    comment.created_at,
                    comment.score,
                    stats,
                )

    @staticmethod
    def _save_mentions(
        session: Session,
        matches,
        stock_ids: dict[str, int],
        source_type: str,
        source_id: str,
        discussion_id: str,
        author: str | None,
        subreddit: str,
        created_at: datetime,
        engagement: float,
        stats: CollectionStats,
    ) -> None:
        # Repeated mentions by one author in one discussion collapse to one weighted observation.
        seen: set[str] = set()
        for ordinal, match in enumerate(matches):
            if match.ticker in seen:
                continue
            seen.add(match.ticker)
            try:
                with session.begin_nested():
                    session.add(
                        TickerMention(
                            stock_id=stock_ids[match.ticker],
                            source_type=source_type,
                            source_reddit_id=source_id,
                            discussion_id=discussion_id,
                            author_hash=author,
                            subreddit=subreddit,
                            created_at=created_at,
                            engagement=max(0, engagement),
                            confidence=match.confidence,
                            ordinal=ordinal,
                        )
                    )
                    session.flush()
            except IntegrityError:
                continue
            stats.mentions += 1
            stats.tickers.add(match.ticker)
