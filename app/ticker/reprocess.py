from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.collectors.service import CollectionStats
from app.config.settings import RadarConfig
from app.database.models import RedditComment, RedditPost, Stock, TickerMention, TickerMetric
from app.ticker.extractor import TickerExtractor


def reprocess_mentions(session: Session, config: RadarConfig) -> CollectionStats:
    """Rebuild derived mentions after updating the stock master."""
    session.execute(delete(TickerMetric))
    session.execute(delete(TickerMention))
    session.flush()
    stats = CollectionStats()
    extractor = TickerExtractor(session, config)
    stock_ids = dict(session.execute(select(Stock.ticker, Stock.id)).all())
    from app.collectors.service import CollectionService

    for post in session.scalars(select(RedditPost).execution_options(yield_per=200)):
        if post.score < config.minimum_post_score:
            continue
        result = extractor.extract(f"{post.title}\n{post.selftext}", post.subreddit)
        stats.filtered += result.filtered_count
        CollectionService._save_mentions(
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
    comments = session.execute(
        select(RedditComment, RedditPost.subreddit, RedditPost.reddit_id)
        .join(RedditPost, RedditPost.id == RedditComment.post_id)
        .execution_options(yield_per=200)
    )
    for comment, subreddit, discussion_id in comments:
        if comment.score < config.minimum_comment_score:
            continue
        result = extractor.extract(comment.body, subreddit)
        stats.filtered += result.filtered_count
        CollectionService._save_mentions(
            session,
            result.matches,
            stock_ids,
            "comment",
            comment.reddit_id,
            discussion_id,
            comment.author_hash,
            subreddit,
            comment.created_at,
            comment.score,
            stats,
        )
    return stats
