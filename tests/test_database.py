from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import RedditPost


def make_post(reddit_id):
    return RedditPost(
        reddit_id=reddit_id,
        subreddit="stocks",
        created_at=datetime.now(UTC),
        title="NVDA",
        selftext="",
        score=1,
        num_comments=0,
        permalink="/x",
    )


def test_duplicate_post_protection(session):
    session.add(make_post("abc"))
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(make_post("abc"))
        session.flush()
