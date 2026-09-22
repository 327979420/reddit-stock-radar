import httpx

from app.collectors.arctic_shift import ArcticShiftClient


async def test_arctic_shift_posts_and_comments_are_normalized():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/posts/search"):
            return httpx.Response(
                200,
                json={"data": [{"id": "post1", "score": 4, "created_utc": 123}]},
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "low", "score": 1, "created_utc": 125},
                    {"id": "high", "score": 20, "created_utc": 124},
                ]
            },
        )

    client = ArcticShiftClient("https://example.test")
    await client.client.aclose()
    client.client = httpx.AsyncClient(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    try:
        posts = [post async for post in client.new_posts("stocks", 1)]
        comments = await client.comments("stocks", "t3_post1", 2)
    finally:
        await client.close()

    assert posts[0]["id"] == "post1"
    assert [comment["id"] for comment in comments] == ["high", "low"]


async def test_unindexed_comments_are_treated_as_empty():
    client = ArcticShiftClient("https://example.test")
    await client.client.aclose()
    client.client = httpx.AsyncClient(
        base_url="https://example.test",
        transport=httpx.MockTransport(lambda _request: httpx.Response(422, json={})),
    )
    try:
        assert await client.comments("stocks", "fresh", 10) == []
    finally:
        await client.close()
