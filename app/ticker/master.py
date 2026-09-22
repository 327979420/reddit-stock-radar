from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Stock


def seed_stocks(session: Session, csv_path: Path | None = None) -> int:
    """Upsert the bundled seed or a full exchange master CSV with the same columns."""
    csv_path = csv_path or Path(__file__).with_name("stocks.csv")
    count = 0
    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = row["ticker"].strip().upper()
            stock = session.scalar(select(Stock).where(Stock.ticker == ticker))
            if stock is None:
                stock = Stock(ticker=ticker, company_name=row["company_name"].strip())
                session.add(stock)
            stock.company_name = row["company_name"].strip()
            stock.aliases = row.get("aliases", "").strip()
            stock.exchange = row.get("exchange", "").strip()
            stock.security_type = row.get("security_type", "Common Stock").strip()
            stock.active = row.get("active", "true").lower() not in {"false", "0", "no"}
            count += 1
    return count
