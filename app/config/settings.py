from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoreWeights(BaseModel):
    mentions: float = 0.25
    unique_authors: float = 0.20
    engagement: float = 0.20
    subreddit_spread: float = 0.10
    momentum: float = 0.25

    @field_validator("momentum")
    @classmethod
    def validate_total(cls, value: float, info: Any) -> float:
        values = dict(info.data)
        values[info.field_name] = value
        if len(values) == 5 and abs(sum(values.values()) - 1.0) > 0.001:
            raise ValueError("heat score weights must total 1.0")
        return value


class DataQualityConfig(BaseModel):
    minimum_daily_posts: int = 1
    volume_drop_warning_ratio: float = 0.25


class HotPostsSummaryConfig(BaseModel):
    enabled: bool = True
    interval_days: int = Field(default=3, ge=2, le=30)
    lookback_hours: int = Field(default=72, ge=24, le=720)
    post_count: int = Field(default=5, ge=1, le=10)
    publish_time: str = "08:10"
    max_post_chars: int = Field(default=3000, ge=500, le=10000)


class RadarConfig(BaseModel):
    subreddits: list[str]
    data_source: Literal["arctic_shift", "reddit_oauth"] = "arctic_shift"
    poll_interval_minutes: int = Field(default=20, ge=5)
    minimum_post_score: int = 2
    minimum_comment_score: int = 2
    comments_per_post: int = Field(default=30, ge=0, le=100)
    posts_per_subreddit: int = Field(default=50, ge=1, le=100)
    hot_posts_for_comments: int = Field(default=15, ge=0, le=100)
    timezone: str = "Australia/Melbourne"
    daily_publish_time: str = "08:00"
    hot_posts_summary: HotPostsSummaryConfig = HotPostsSummaryConfig()
    weights: ScoreWeights = ScoreWeights()
    blacklist: set[str] = set()
    stock_context_keywords: list[str] = []
    aliases: dict[str, list[str]] = {}
    data_quality: DataQualityConfig = DataQualityConfig()


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "reddit-stock-radar/0.1"
    arctic_shift_base_url: str = "https://arctic-shift.photon-reddit.com"
    discord_bot_token: str = ""
    discord_channel_id: int | None = None
    discord_webhook_url: str = ""
    openai_api_key: str = ""
    openai_summary_model: str = "gpt-5.6-luna"
    database_url: str = "sqlite:///data/radar.db"
    radar_config: str = "app/config/default.yaml"
    log_level: str = "INFO"

    @field_validator("discord_channel_id", mode="before")
    @classmethod
    def empty_channel_id_is_none(cls, value: Any) -> Any:
        return None if value == "" else value


def load_config(path: str | Path) -> RadarConfig:
    with Path(path).open(encoding="utf-8") as handle:
        return RadarConfig.model_validate(yaml.safe_load(handle))
