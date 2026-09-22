from pathlib import Path

import pytest

from app.config import RadarConfig
from app.database import Database
from app.ticker.master import seed_stocks


@pytest.fixture
def session(tmp_path: Path):
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    with db.session() as current:
        seed_stocks(current)
        yield current


@pytest.fixture
def config():
    return RadarConfig(
        subreddits=["stocks"],
        blacklist={"AI", "IT", "ON", "ALL", "ARE", "FOR", "SO"},
        stock_context_keywords=["stock", "shares", "calls", "puts", "buy", "earnings"],
    )
