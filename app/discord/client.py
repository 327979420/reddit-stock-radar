from __future__ import annotations

import httpx

from app.discord.formatter import split_discord_message


class DiscordSender:
    def __init__(self, token: str):
        self.token = token

    async def send(self, channel_id: int, content: str) -> str:
        message_id = ""
        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in split_discord_message(content):
                response = await client.post(
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
                response = await client.post(
                    self.webhook_url,
                    params={"wait": "true"},
                    json={"content": chunk, "allowed_mentions": {"parse": []}, "flags": 4},
                )
                response.raise_for_status()
                message_id = response.json()["id"]
        return message_id

    async def send_embed(self, embed: dict) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.webhook_url,
                params={"wait": "true"},
                json={"embeds": [embed], "allowed_mentions": {"parse": []}},
            )
            response.raise_for_status()
            return response.json()["id"]
