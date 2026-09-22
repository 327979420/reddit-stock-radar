from __future__ import annotations

from datetime import datetime

from app.scoring.service import MetricRow


def rank_marker(change: int | None) -> str:
    if change is None:
        return "NEW"
    if change > 0:
        return f"↑{change}"
    if change < 0:
        return f"↓{abs(change)}"
    return "—"


def pct(value: float | None, trend: str = "") -> str:
    if value is None:
        return "BREAK" if trend == "New / Breakout" else "N/A"
    return f"{value:+.0f}%"


def format_radar(rows: list[MetricRow], now: datetime, window: str = "24h", limit: int = 20) -> str:
    title = f"🔥 **Reddit 美股热度榜 · {window}｜{now:%d %b}**"
    table = [f"{'#':>2} {'TICKER':<10} {'HEAT':>4} {'MENT':>6} {'24H':>8} {'RANK':>5}"]
    for row in rows[:limit]:
        table.append(
            f"{row.rank:>2} {row.ticker:<10} {row.heat_score:>4.0f} "
            f"{row.mentions:>6,} {pct(row.momentum_pct, row.trend):>8} "
            f"{rank_marker(row.rank_change):>5}"
        )
    lines = [title, f"```text\n{'\n'.join(table)}\n```"]
    rising = sorted(rows, key=lambda row: row.momentum_pct or -9999, reverse=True)[:3]
    new = [row.ticker for row in rows if row.trend == "New / Breakout"][:5]
    falling = sorted(
        (row for row in rows if (row.momentum_pct or 0) < 0),
        key=lambda row: row.momentum_pct or 0,
    )[:3]
    if rising:
        lines.append(
            "🔥 **升温** · "
            + " · ".join(f"{row.ticker} {pct(row.momentum_pct, row.trend)}" for row in rising)
        )
    if new:
        lines.append("🆕 **突破** · " + " · ".join(new))
    if falling:
        lines.append(
            "📉 **降温** · "
            + " · ".join(f"{row.ticker} {pct(row.momentum_pct)}" for row in falling)
        )
    return "\n".join(lines).strip()


def split_discord_message(message: str, limit: int = 2000) -> list[str]:
    chunks: list[str] = []
    current = ""
    for block in message.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
