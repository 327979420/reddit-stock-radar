import asyncio

import pytest

from app.jobs.service import RadarJobs


@pytest.mark.asyncio
async def test_scheduled_jobs_are_serialized(monkeypatch):
    jobs = RadarJobs(None, None, None)  # type: ignore[arg-type]
    collection_started = asyncio.Event()
    release_collection = asyncio.Event()
    publisher_started = asyncio.Event()

    async def collect():
        collection_started.set()
        await release_collection.wait()

    async def publish(_force=False):
        publisher_started.set()
        return True

    monkeypatch.setattr(jobs, "_collect", collect)
    monkeypatch.setattr(jobs, "_publish", publish)

    collection_task = asyncio.create_task(jobs.collect())
    await collection_started.wait()
    publisher_task = asyncio.create_task(jobs.publish())
    await asyncio.sleep(0)

    assert not publisher_started.is_set()

    release_collection.set()
    assert await publisher_task is True
    await collection_task
