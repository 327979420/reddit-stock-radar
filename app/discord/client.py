from __future__ import annotations

import logging

import httpx

from app.discord.formatter import split_discord_message
from app.retry import retry_async

logger = logging.getLogger(__name__)


async def _post_with_wake_retry(client: httpx.AsyncClient, *args, **kwargs) -> httpx.Response:
    # Retrying only connection-establishment failures avoids duplicating a message
    # after an ambiguous response/read timeout.
    return await retry_async(
        lambda: client.post(*args, **kwargs),
        retry_on=(httpx.ConnectError, httpx.ConnectTimeout),
        logger=logger,
        operation_name="discord_post",
    )


class DiscordSender:
    def __init__(self, token: str):
        self.token = token

    async def send(self, channel_id: int, content: str) -> str:
        message_id = ""
        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in split_discord_message(content):
                response = await _post_with_wake_retry(
                    client,
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers={"Authorization": f"Bot {self.token}"},
                    json={"content": chunk, "allowed_mentions": {"parse": []}, "flags": 4},
                )
                response.raise_for_status()
                message_id = response.json()["id"]
        return message_id


class DiscordWebhookSender:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, content: str) -> str:
        message_id = ""
        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in split_discord_message(content):
                response = await _post_with_wake_retry(
                    client,
                    self.webhook_url,
                    params={"wait": "true"},
                    json={"content": chunk, "allowed_mentions": {"parse": []}, "flags": 4},
                )
                response.raise_for_status()
                message_id = response.json()["id"]
        return message_id

    async def send_embed(self, embed: dict) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await _post_with_wake_retry(
                client,
                self.webhook_url,
                params={"wait": "true"},
                json={"embeds": [embed], "allowed_mentions": {"parse": []}},
            )
            response.raise_for_status()
            return response.json()["id"]
