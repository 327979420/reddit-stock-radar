from dataclasses import replace
from datetime import UTC, datetime

from app.discord.formatter import (
    format_radar,
    rank_marker,
    short_company,
    split_discord_message,
)
from app.scoring.service import MetricRow


def metric():
    return MetricRow(
        1,
        "NVDA",
        "NVIDIA Corporation",
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
    rows = [
        replace(metric(), ticker=ticker, rank=rank, momentum_pct=change, trend=trend)
        for rank, (ticker, change, trend) in enumerate(
            [
                ("NVDA", 32, "Rising"),
                ("TSLA", -40, "Falling"),
                ("AMD", 10, "Rising"),
                ("CSCO", None, "New / Breakout"),
                ("MU", -5, "Falling"),
            ],
            1,
        )
    ]
    text = format_radar(rows, datetime(2026, 8, 13, tzinfo=UTC))
    assert text.startswith("## 🔥 Reddit 美股热度榜 · 8月13日")
    assert "### 🥇 NVDA · NVIDIA" in text
    assert "-# 热度 96 · 提及 3,420 · 24h +32% · 排名 ↑3" in text
    assert "```text" in text
    assert "TICKER" in text
    assert " 4  CSCO" in text
    assert "NEW" in text
    assert "📈 **升温**　NVDA +32% · AMD +10%" in text
    assert "🆕 **新上榜**　CSCO" in text
    assert "📉 **降温**　TSLA -40% · MU -5%" in text
    assert "\n\n" not in text
    assert all(len(chunk) <= 2000 for chunk in split_discord_message(text))


def test_rising_excludes_falling_tickers():
    rows = [replace(metric(), momentum_pct=-10, trend="Falling")]
    text = format_radar(rows, datetime(2026, 8, 13, tzinfo=UTC))
    assert "升温" not in text
    assert "```" not in text


def test_short_company_names():
    assert short_company("MICRON TECHNOLOGY INC", "MU") == "Micron Technology"
    assert short_company("NVIDIA Corporation", "NVDA") == "NVIDIA"
    assert short_company("Taiwan Semiconductor Manufacturing Company", "TSM") == (
        "Taiwan Semiconductor…"
    )
    assert short_company("INVESCO QQQ TRUST, SERIES 1", "QQQ") == "Invesco QQQ"
    assert short_company("SPDR S&P 500 ETF Trust", "SPY") == "SPDR S&P 500 ETF"
    assert short_company("JPMorgan Chase & Co.", "JPM") == "JPMorgan Chase"
    assert short_company("Alphabet Inc. Class A", "GOOGL") == "Alphabet"
    assert short_company("", "XYZ") == ""
