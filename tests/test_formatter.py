from datetime import UTC, datetime

from app.discord.formatter import format_radar, rank_marker, split_discord_message
from app.scoring.service import MetricRow


def metric():
    return MetricRow(
        1,
        "NVDA",
        "NVIDIA",
        3420,
        500,
        100,
        50,
        5,
        1000,
        2000,
        1000,
        momentum_pct=32,
        trend="Rising",
        heat_score=96,
        rank=1,
        rank_change=3,
    )


def test_rank_markers():
    assert rank_marker(3) == "↑3"
    assert rank_marker(-2) == "↓2"
    assert rank_marker(0) == "—"
    assert rank_marker(None) == "NEW"


def test_discord_format():
    text = format_radar([metric()], datetime(2026, 8, 13, tzinfo=UTC))
    assert "NVDA" in text
    assert "TICKER" in text
    assert "HEAT" in text
    assert "  96" in text
    assert "+32%" in text
    assert "```text" in text
    assert "\n\n" not in text
    assert all(len(chunk) <= 2000 for chunk in split_discord_message(text))
