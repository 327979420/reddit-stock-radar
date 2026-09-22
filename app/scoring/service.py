from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.config.settings import ScoreWeights
from app.database.models import Stock, TickerMention, TickerMetric

WINDOWS = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720, "90d": 2160}


@dataclass
class MetricRow:
    stock_id: int
    ticker: str
    company: str
    mentions: int
    unique_authors: int
    unique_posts: int
    unique_comments: int
    unique_subreddits: int
    engagement: float
    previous_mentions: int
    seven_day_average: float
    momentum_pct: float | None = None
    trend: str = "Stable"
    heat_score: float = 0
    rank: int = 0
    rank_change: int | None = None


def momentum(current: int, previous: int, baseline: float = 0) -> tuple[float | None, str]:
    if current > 0 and previous == 0 and baseline < 1:
        return None, "New / Breakout"
    denominator = previous if previous > 0 else max(baseline, 1)
    change = ((current - denominator) / denominator) * 100
    if previous == 0 and current >= max(3, baseline * 2) and change >= 100:
        trend = "New / Breakout"
    elif change >= 20:
        trend = "Rising"
    elif change <= -20:
        trend = "Falling"
    else:
        trend = "Stable"
    return round(change, 1), trend


def _log_normalize(value: float, maximum: float) -> float:
    if value <= 0 or maximum <= 0:
        return 0
    return math.log1p(value) / math.log1p(maximum)


def assign_scores(rows: list[MetricRow], weights: ScoreWeights) -> list[MetricRow]:
    if not rows:
        return rows
    maxima = {
        "mentions": max(row.mentions for row in rows),
        "authors": max(row.unique_authors for row in rows),
        "engagement": max(row.engagement for row in rows),
        "spread": max(row.unique_subreddits for row in rows),
        "momentum": max(max(row.momentum_pct or 0, 0) for row in rows),
    }
    for row in rows:
        positive_momentum = max(
            row.momentum_pct or (200 if row.trend == "New / Breakout" else 0), 0
        )
        raw = (
            weights.mentions * _log_normalize(row.mentions, maxima["mentions"])
            + weights.unique_authors * _log_normalize(row.unique_authors, maxima["authors"])
            + weights.engagement * _log_normalize(row.engagement, maxima["engagement"])
            + weights.subreddit_spread * _log_normalize(row.unique_subreddits, maxima["spread"])
            + weights.momentum * _log_normalize(positive_momentum, max(maxima["momentum"], 200))
        )
        row.heat_score = round(min(100, raw * 100), 1)
    rows.sort(key=lambda row: (row.heat_score, row.mentions, row.unique_authors), reverse=True)
    for rank, row in enumerate(rows, 1):
        row.rank = rank
    return rows


class ScoringService:
    def __init__(self, weights: ScoreWeights):
        self.weights = weights

    def calculate(
        self, session: Session, window: str = "24h", as_of: datetime | None = None
    ) -> list[MetricRow]:
        as_of = (as_of or datetime.now(UTC)).astimezone(UTC)
        hours = WINDOWS[window]
        start = as_of - timedelta(hours=hours)
        previous_start = start - timedelta(hours=hours)
        seven_start = as_of - timedelta(days=7)
        current = self._aggregate(session, start, as_of)
        previous = {
            row.stock_id: row.mentions for row in self._aggregate(session, previous_start, start)
        }
        seven = {
            row.stock_id: row.mentions / 7 for row in self._aggregate(session, seven_start, as_of)
        }
        for row in current:
            row.previous_mentions = previous.get(row.stock_id, 0)
            row.seven_day_average = seven.get(row.stock_id, 0)
            row.momentum_pct, row.trend = momentum(
                row.mentions, row.previous_mentions, row.seven_day_average
            )
        assign_scores(current, self.weights)
        self._apply_rank_changes(session, current, window, as_of)
        self._save(session, current, window, as_of)
        return current

    @staticmethod
    def _aggregate(session: Session, start: datetime, end: datetime) -> list[MetricRow]:
        query = (
            select(
                Stock.id,
                Stock.ticker,
                Stock.company_name,
                func.count(TickerMention.id),
                func.count(distinct(TickerMention.author_hash)),
                func.count(distinct(TickerMention.discussion_id)),
                func.count(
                    distinct(
                        case(
                            (TickerMention.source_type == "comment", TickerMention.source_reddit_id)
                        )
                    )
                ),
                func.count(distinct(TickerMention.subreddit)),
                func.coalesce(func.sum(func.log(1 + TickerMention.engagement)), 0),
            )
            .join(TickerMention, TickerMention.stock_id == Stock.id)
            .where(TickerMention.created_at >= start, TickerMention.created_at < end)
            .group_by(Stock.id)
        )
        return [
            MetricRow(*row, previous_mentions=0, seven_day_average=0)
            for row in session.execute(query)
        ]

    @staticmethod
    def _apply_rank_changes(
        session: Session, rows: list[MetricRow], window: str, as_of: datetime
    ) -> None:
        prior_time = session.scalar(
            select(func.max(TickerMetric.as_of)).where(
                TickerMetric.window == window, TickerMetric.as_of < as_of - timedelta(hours=12)
            )
        )
        if prior_time is None:
            return
        prior_rows = session.execute(
            select(TickerMetric.stock_id, TickerMetric.rank).where(
                TickerMetric.window == window, TickerMetric.as_of == prior_time
            )
        )
        prior = {stock_id: rank for stock_id, rank in prior_rows}
        for row in rows:
            row.rank_change = prior[row.stock_id] - row.rank if row.stock_id in prior else None

    @staticmethod
    def _save(session: Session, rows: list[MetricRow], window: str, as_of: datetime) -> None:
        for row in rows:
            metric = session.scalar(
                select(TickerMetric).where(
                    TickerMetric.stock_id == row.stock_id,
                    TickerMetric.window == window,
                    TickerMetric.as_of == as_of,
                )
            ) or TickerMetric(stock_id=row.stock_id, window=window, as_of=as_of)
            session.add(metric)
            for field in (
                "mentions",
                "unique_authors",
                "unique_posts",
                "unique_comments",
                "unique_subreddits",
                "engagement",
                "momentum_pct",
                "trend",
                "heat_score",
                "rank",
                "rank_change",
            ):
                setattr(metric, field, getattr(row, field))
