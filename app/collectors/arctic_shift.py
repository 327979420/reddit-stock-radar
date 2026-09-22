from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class ArcticShiftError(RuntimeError):
    pass


@dataclass
class ArcticShiftClient:
    base_url: str = "https://arctic-shift.photon-reddit.com"
    max_retries: int = 5

    def __post_init__(self) -> None:
        self.client = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=45,
            headers={"User-Agent": "reddit-stock-radar/0.1"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        for attempt in range(self.max_retries):
            try:
                response = await self.client.get(path, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = float(response.headers.get("retry-after", 0) or 0)
                    delay = max(retry_after, min(60, 2**attempt + random.random()))
                    logger.warning(
                        "arctic_shift_retry status=%s delay=%.1f", response.status_code, delay
                    )
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise ArcticShiftError("Unexpected Arctic Shift response format")
                return payload["data"]
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt == self.max_retries - 1:
                    raise ArcticShiftError(str(exc)) from exc
                await asyncio.sleep(min(60, 2**attempt + random.random()))
        raise ArcticShiftError(f"Arctic Shift request failed after retries: {path}")

    async def new_posts(self, subreddit: str, limit: int = 50) -> AsyncIterator[dict[str, Any]]:
        rows = await self.request(
            "/api/posts/search",
            {
                "subreddit": subreddit,
                "limit": min(limit, 100),
                "sort": "desc",
                "fields": "id,subreddit,author,created_utc,title,selftext,score,num_comments,url",
            },
        )
        for row in rows[:limit]:
            url = str(row.get("url") or "")
            if "reddit.com" in url:
                row["permalink"] = urlparse(url).path
            yield row

    async def comments(self, subreddit: str, post_id: str, limit: int = 30) -> list[dict[str, Any]]:
        # Arctic Shift sorts searches by creation time. Fetch extra rows and retain the
        # highest-score comments locally so the scoring input remains engagement-focused.
        try:
            rows = await self.request(
                "/api/comments/search",
                {
                    "link_id": post_id.removeprefix("t3_"),
                    "limit": min(max(limit * 3, limit), 100),
                    "sort": "desc",
                    "fields": "id,author,created_utc,body,score,link_id,parent_id",
                },
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {404, 422}:
                # Very recent posts may be visible before their comment index exists.
                logger.info("arctic_shift_comments_not_indexed post_id=%s", post_id)
                return []
            raise
        rows.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
        return rows[:limit]
