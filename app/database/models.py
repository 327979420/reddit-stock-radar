from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[str] = mapped_column(Text, default="")
    exchange: Mapped[str] = mapped_column(String(20), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    security_type: Mapped[str] = mapped_column(String(50), default="Common Stock")


class RedditPost(Base):
    __tablename__ = "reddit_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    reddit_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    subreddit: Mapped[str] = mapped_column(String(50), index=True)
    author_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(Text)
    selftext: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    upvote_ratio: Mapped[float | None] = mapped_column(Float)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    permalink: Mapped[str] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RedditComment(Base):
    __tablename__ = "reddit_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    reddit_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("reddit_posts.id"), index=True)
    author_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    body: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    post: Mapped[RedditPost] = relationship()


class TickerMention(Base):
    __tablename__ = "ticker_mentions"
    __table_args__ = (
        UniqueConstraint(
            "stock_id", "source_type", "source_reddit_id", "ordinal", name="uq_mention"
        ),
        Index("ix_mentions_created_stock", "created_at", "stock_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(10))
    source_reddit_id: Mapped[str] = mapped_column(String(20))
    discussion_id: Mapped[str] = mapped_column(String(20), index=True)
    author_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    subreddit: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    engagement: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=1)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[Stock] = relationship()


class TickerMetric(Base):
    __tablename__ = "ticker_metrics"
    __table_args__ = (UniqueConstraint("stock_id", "window", "as_of", name="uq_metric"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    window: Mapped[str] = mapped_column(String(10), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    mentions: Mapped[int] = mapped_column(Integer)
    unique_authors: Mapped[int] = mapped_column(Integer)
    unique_posts: Mapped[int] = mapped_column(Integer)
    unique_comments: Mapped[int] = mapped_column(Integer)
    unique_subreddits: Mapped[int] = mapped_column(Integer)
    engagement: Mapped[float] = mapped_column(Float)
    momentum_pct: Mapped[float | None] = mapped_column(Float)
    trend: Mapped[str] = mapped_column(String(20))
    heat_score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    rank_change: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[Stock] = relationship()


class DiscordPost(Base):
    __tablename__ = "discord_posts"
    __table_args__ = (
        UniqueConstraint("channel_id", "report_date", "window", name="uq_discord_report"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(30))
    report_date: Mapped[date] = mapped_column(Date)
    window: Mapped[str] = mapped_column(String(10))
    message_id: Mapped[str | None] = mapped_column(String(30))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posts_processed: Mapped[int] = mapped_column(Integer, default=0)
    comments_processed: Mapped[int] = mapped_column(Integer, default=0)
    ticker_mentions_detected: Mapped[int] = mapped_column(Integer, default=0)
    unique_tickers: Mapped[int] = mapped_column(Integer, default=0)
    api_errors: Mapped[int] = mapped_column(Integer, default=0)
    false_positive_filtered: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")
