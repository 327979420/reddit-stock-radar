from __future__ import annotations

import re
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.database.models import RedditPost


@dataclass(frozen=True)
class SummaryPost:
    title: str
    subreddit: str
    score: int
    comments: int
    permalink: str
    text: str


# Megathreads such as "Daily Discussion Thread" top every engagement sort, but their
# body is empty, so a summary of them says nothing.
RECURRING_THREAD = re.compile(
    r"\b(daily|weekend|weekly)\b.*\b(discussion|thread)\b|what are your moves tomorrow",
    re.IGNORECASE,
)


def is_recurring_thread(title: str) -> bool:
    return bool(RECURRING_THREAD.search(title))


class PostDigest(BaseModel):
    index: int
    summary: str = Field(max_length=120)


class HotPostsDigest(BaseModel):
    overview: str = Field(max_length=220)
    posts: list[PostDigest]


def prepare_posts(posts: list[RedditPost], max_chars: int) -> list[SummaryPost]:
    return [
        SummaryPost(
            title=post.title,
            subreddit=post.subreddit,
            score=post.score,
            comments=post.num_comments,
            permalink=f"https://www.reddit.com{post.permalink}",
            text=post.selftext[:max_chars],
        )
        for post in posts
    ]


def build_prompt(posts: list[SummaryPost]) -> str:
    source = "\n\n".join(
        f"[{index}] r/{post.subreddit} | score {post.score} | comments {post.comments}\n"
        f"Title: {post.title}\nBody: {post.text or '(no body)'}"
        for index, post in enumerate(posts, 1)
    )
    return f"""请根据下列 Reddit 帖子生成一份简洁的中文“热门帖子”摘要，供美股投资社区阅读。

要求：
- overview 用不超过 80 个中文字概括共同话题和市场情绪，只写 1-2 句。
- posts 必须为每个帖子生成一条摘要，index 与输入编号严格对应。
- 每条 summary 只写核心观点、重要依据或争议，不超过 55 个中文字。
- 严格依据提供的内容；不要编造事实、价格、财务数据或投资建议。
- 对明显的个人观点或未经证实说法标注“网友观点”。
- 不写链接、免责声明、标题复述或 Markdown。

帖子：
{source}"""


class HotPostsSummarizer:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def summarize(self, posts: list[SummaryPost]) -> HotPostsDigest:
        response = await self.client.responses.parse(
            model=self.model,
            input=build_prompt(posts),
            text_format=HotPostsDigest,
            reasoning={"effort": "low"},
        )
        if response.output_parsed is None:
            raise RuntimeError("OpenAI returned an empty hot-post summary")
        return response.output_parsed


def build_hot_posts_embed(digest: HotPostsDigest, posts: list[SummaryPost]) -> dict:
    summaries = {item.index: item.summary for item in digest.posts}
    fields = []
    for index, post in enumerate(posts, 1):
        # Lead with the Chinese takeaway; the English title and stats are supporting detail.
        fields.append(
            {
                "name": f"{index}｜{summaries.get(index, '本帖暂无摘要。')[:180]}",
                "value": (
                    f"*{post.title[:100]}*\n"
                    f"`r/{post.subreddit}`  ↑ {post.score:,}  💬 {post.comments:,}  "
                    f"[原帖 ↗]({post.permalink})"
                ),
                "inline": False,
            }
        )
    return {
        "title": "🔥 Reddit 热帖｜过去 72 小时",
        "description": f"> {digest.overview[:300]}",
        "color": 0xF97316,
        "fields": fields,
        "footer": {"text": "Reddit Stock Radar · AI 摘要 · 网友观点，非投资建议"},
    }
