from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RedditApiError(RuntimeError):
    pass


@dataclass
class RedditClient:
    client_id: str
    client_secret: str
    user_agent: str
    max_retries: int = 5

    def __post_init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=30, headers={"User-Agent": self.user_agent})
        self._token: str | None = None
        self._token_expires_at = 0.0

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at - 60:
            return self._token
        response = await self.client.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.monotonic() + int(payload.get("expires_in", 3600))
        return self._token

    async def request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(self.max_retries):
            token = await self._get_token()
            try:
                response = await self.client.get(
                    f"https://oauth.reddit.com{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if response.status_code == 401:
                    self._token = None
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = float(response.headers.get("retry-after", 0) or 0)
                    delay = max(retry_after, min(60, 2**attempt + random.random()))
                    logger.warning("reddit_retry status=%s delay=%.1f", response.status_code, delay)
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                remaining = response.headers.get("x-ratelimit-remaining")
                reset = response.headers.get("x-ratelimit-reset")
                if remaining is not None and float(remaining) < 2:
                    await asyncio.sleep(min(float(reset or 1), 60))
                return response.json()
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt == self.max_retries - 1:
                    raise RedditApiError(str(exc)) from exc
                await asyncio.sleep(min(60, 2**attempt + random.random()))
        raise RedditApiError(f"Reddit request failed after retries: {path}")

    async def new_posts(self, subreddit: str, limit: int = 50) -> AsyncIterator[dict[str, Any]]:
        after = None
        fetched = 0
        while fetched < limit:
            page_size = min(100, limit - fetched)
            payload = await self.request(
                f"/r/{subreddit}/new",
                {"limit": page_size, "after": after, "raw_json": 1},
            )
            children = payload.get("data", {}).get("children", [])
            for child in children:
                yield child["data"]
                fetched += 1
            after = payload.get("data", {}).get("after")
            if not after or not children:
                break

    async def comments(self, subreddit: str, post_id: str, limit: int = 30) -> list[dict[str, Any]]:
        payload = await self.request(
            f"/r/{subreddit}/comments/{post_id}",
            {"limit": limit, "depth": 2, "sort": "top", "raw_json": 1},
        )
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        output: list[dict[str, Any]] = []

        def walk(children: list[dict[str, Any]]) -> None:
            for child in children:
                if child.get("kind") != "t1" or len(output) >= limit:
                    continue
                data = child.get("data", {})
                output.append(data)
                replies = data.get("replies")
                if isinstance(replies, dict):
                    walk(replies.get("data", {}).get("children", []))

        walk(payload[1].get("data", {}).get("children", []))
        return output
