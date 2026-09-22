from app.config.settings import ScoreWeights
from app.scoring.service import MetricRow, assign_scores, momentum


def row(ticker, mentions, authors, engagement, spread, momentum_pct):
    return MetricRow(
        1,
        ticker,
        ticker,
        mentions,
        authors,
        1,
        1,
        spread,
        engagement,
        0,
        0,
        momentum_pct=momentum_pct,
    )


def test_momentum_rising():
    change, trend = momentum(620, 180, 100)
    assert change == 244.4
    assert trend == "Rising"


def test_momentum_breakout():
    change, trend = momentum(5, 0, 0)
    assert change is None
    assert trend == "New / Breakout"


def test_heat_score_is_ranked_and_bounded():
    rows = [row("AAA", 100, 50, 1000, 4, 100), row("BBB", 10, 8, 20, 1, -20)]
    assign_scores(rows, ScoreWeights())
    assert rows[0].ticker == "AAA"
    assert rows[0].rank == 1
    assert 0 <= rows[0].heat_score <= 100
    assert rows[1].rank == 2
