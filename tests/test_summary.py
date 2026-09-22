from datetime import UTC, datetime

from app.database.models import RedditPost
from app.summary.service import (
    HotPostsDigest,
    PostDigest,
    build_hot_posts_embed,
    build_prompt,
    prepare_posts,
)


def post():
    return RedditPost(
        reddit_id="abc",
        subreddit="stocks",
        created_at=datetime.now(UTC),
        title="NVDA earnings discussion",
        selftext="Revenue was debated by commenters.",
        score=1200,
        num_comments=300,
        permalink="/r/stocks/comments/abc/example/",
    )


def test_summary_prompt_and_format_keep_source_mapping():
    posts = prepare_posts([post()], 3000)
    prompt = build_prompt(posts)
    assert "[1]" in prompt
    assert "不要编造" in prompt
    digest = HotPostsDigest(
        overview="本期关注财报。", posts=[PostDigest(index=1, summary="网友讨论增长。")]
    )
    embed = build_hot_posts_embed(digest, posts)
    assert embed["title"] == "🔥 热门帖子｜过去 72 小时"
    assert len(embed["fields"]) == 1
    assert "https://www.reddit.com/r/stocks/comments/abc/example/" in embed["fields"][0]["value"]
    assert "↑ 1,200" in embed["fields"][0]["value"]
    assert "网友讨论增长" in embed["fields"][0]["value"]
