from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import RadarConfig
from app.database.models import Stock

CASHTAG = re.compile(r"(?<!\w)\$([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?!\w)")
UPPERCASE = re.compile(r"(?<![$\w])([A-Z]{2,5}(?:\.[A-Z])?)(?!\w)")


@dataclass(frozen=True)
class Match:
    ticker: str
    confidence: float
    start: int
    method: str


@dataclass(frozen=True)
class ExtractionResult:
    matches: list[Match]
    filtered_count: int = 0


class TickerExtractor:
    """Precision-first extraction using a stock master, aliases and context."""

    def __init__(self, session: Session, config: RadarConfig):
        stocks = session.scalars(select(Stock).where(Stock.active.is_(True))).all()
        self.stocks = {stock.ticker.upper(): stock for stock in stocks}
        self.blacklist = {word.upper() for word in config.blacklist}
        self.context = tuple(word.lower() for word in config.stock_context_keywords)
        aliases: dict[str, set[str]] = {}
        for stock in stocks:
            values = [stock.company_name, *(stock.aliases.split("|") if stock.aliases else [])]
            values.extend(config.aliases.get(stock.ticker, []))
            for value in values:
                clean = value.strip()
                if len(clean) >= 4:
                    aliases.setdefault(clean.casefold(), set()).add(stock.ticker)
        self.aliases = aliases
        alias_terms = sorted(aliases, key=len, reverse=True)
        self.alias_pattern = (
            re.compile(
                rf"(?<!\w)({'|'.join(re.escape(alias) for alias in alias_terms)})(?!\w)",
                re.IGNORECASE,
            )
            if alias_terms
            else None
        )

    def extract(self, text: str, subreddit: str = "") -> ExtractionResult:
        found: dict[tuple[str, int], Match] = {}
        filtered = 0
        for match in CASHTAG.finditer(text):
            ticker = match.group(1).upper()
            if ticker in self.stocks:
                found[(ticker, match.start())] = Match(ticker, 1.0, match.start(), "cashtag")
            else:
                filtered += 1

        for match in UPPERCASE.finditer(text):
            ticker = match.group(1)
            if ticker not in self.stocks:
                continue
            if ticker in self.blacklist:
                filtered += 1
                continue
            found.setdefault((ticker, match.start()), Match(ticker, 0.85, match.start(), "symbol"))

        if self.alias_pattern:
            for match in self.alias_pattern.finditer(text):
                tickers = self.aliases[match.group(1).casefold()]
                if len(tickers) != 1:
                    # Ambiguous company names (e.g. Google share classes) require a symbol.
                    continue
                ticker = next(iter(tickers))
                found.setdefault(
                    (ticker, match.start()), Match(ticker, 0.9, match.start(), "company")
                )

        return ExtractionResult(sorted(found.values(), key=lambda item: item.start), filtered)
