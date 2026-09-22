from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Stock

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUPPORTED_EXCHANGES = {"Nasdaq", "NYSE"}


def update_from_sec(session: Session, user_agent: str) -> int:
    """Upsert the SEC company/ticker/exchange file, excluding OTC securities."""
    response = httpx.get(
        SEC_TICKERS_URL,
        headers={"User-Agent": user_agent or "reddit-stock-radar/0.1 admin@example.com"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    fields = payload["fields"]
    count = 0
    for values in payload["data"]:
        row = dict(zip(fields, values, strict=True))
        if row["exchange"] not in SUPPORTED_EXCHANGES or not row["ticker"]:
            continue
        ticker = str(row["ticker"]).upper()
        stock = session.scalar(select(Stock).where(Stock.ticker == ticker))
        if stock is None:
            stock = Stock(ticker=ticker, company_name=str(row["name"]), aliases="")
            session.add(stock)
        stock.company_name = str(row["name"])
        stock.exchange = str(row["exchange"])
        stock.active = True
        stock.security_type = stock.security_type or "SEC registrant"
        count += 1
    return count
