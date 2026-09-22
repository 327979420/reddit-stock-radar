from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class RedditDataClient(Protocol):
    async def close(self) -> None: ...

    def new_posts(self, subreddit: str, limit: int = 50) -> AsyncIterator[dict[str, Any]]: ...

    async def comments(
        self, subreddit: str, post_id: str, limit: int = 30
    ) -> list[dict[str, Any]]: ...
