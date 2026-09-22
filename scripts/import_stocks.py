"""Import a full NYSE/NASDAQ/AMEX CSV matching app/ticker/stocks.csv columns."""

import argparse
from pathlib import Path

from app.config import AppSettings
from app.database import Database
from app.ticker.master import seed_stocks

parser = argparse.ArgumentParser()
parser.add_argument("csv", type=Path)
args = parser.parse_args()
db = Database(AppSettings().database_url)
db.create_all()
with db.session() as session:
    count = seed_stocks(session, args.csv)
print(f"Imported {count} stock rows")
