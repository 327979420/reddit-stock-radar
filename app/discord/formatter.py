from __future__ import annotations

from datetime import datetime

from app.scoring.service import MetricRow

MEDALS = ("🥇", "🥈", "🥉")


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
        return "NEW" if trend == "New / Breakout" else "N/A"
    return f"{value:+.0f}%"


def window_label(window: str) -> str:
    return window.replace("h", " 小时").replace("d", " 天")


def format_radar(rows: list[MetricRow], now: datetime, window: str = "24h", limit: int = 20) -> str:
    rows = rows[:limit]
    lines = [
        f"## 🔥 Reddit 美股热度榜 · {now.month}月{now.day}日",
        f"-# 过去 {window_label(window)} · 热度综合提及、作者、互动、扩散与动能，满分 100",
    ]
    # The top three are the headline; Discord headings give them real visual weight.
    for medal, row in zip(MEDALS, rows):
        company = f" · {row.company[:24]}" if row.company and row.company != row.ticker else ""
        lines.append(f"### {medal} {row.ticker}{company}")
        lines.append(
            f"-# 热度 {row.heat_score:.0f} · 提及 {row.mentions:,} · "
            f"{window} {pct(row.momentum_pct, row.trend)} · 排名 {rank_marker(row.rank_change)}"
        )
    if len(rows) > len(MEDALS):
        table = [f"{'#':>2}  {'TICKER':<7} {'HEAT':>4} {'MENT':>5} {window.upper():>6}"]
        for row in rows[len(MEDALS) :]:
            table.append(
                f"{row.rank:>2}  {row.ticker:<7} {row.heat_score:>4.0f} "
                f"{row.mentions:>5,} {pct(row.momentum_pct, row.trend):>6}"
            )
        lines.append(f"```text\n{'\n'.join(table)}\n```")
    rising = sorted(
        (row for row in rows if (row.momentum_pct or 0) > 0),
        key=lambda row: row.momentum_pct or 0,
        reverse=True,
    )[:3]
    new = [row.ticker for row in rows if row.trend == "New / Breakout"][:5]
    falling = sorted(
        (row for row in rows if (row.momentum_pct or 0) < 0),
        key=lambda row: row.momentum_pct or 0,
    )[:3]
    if rising:
        lines.append(
            "📈 **升温**　" + " · ".join(f"{row.ticker} {pct(row.momentum_pct)}" for row in rising)
        )
    if new:
        lines.append("🆕 **新上榜**　" + " · ".join(new))
    if falling:
        lines.append(
            "📉 **降温**　" + " · ".join(f"{row.ticker} {pct(row.momentum_pct)}" for row in falling)
        )
    lines.append("-# 热度反映讨论关注度，不预测价格，非投资建议")
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
