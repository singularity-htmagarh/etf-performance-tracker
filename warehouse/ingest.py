"""
warehouse/ingest.py
---------------------
ETL job: pulls fund metadata + daily prices from Yahoo Finance (via the
existing data_engine.py fetchers) and loads them into the DuckDB
warehouse, one region at a time, into separate US / Canada schemas.
 
Run directly:
    python -m warehouse.ingest                 # both regions
    python -m warehouse.ingest --region US      # US only
    python -m warehouse.ingest --region Canada  # Canada only
    python -m warehouse.ingest --period 5y      # longer price history
 
This is also what the Streamlit app's "Sync from Yahoo Finance" sidebar
button calls under the hood — same function, so a scheduled run (cron,
GitHub Actions, Prefect flow — matches the pattern already used for
Heath's other DuckDB pipelines) and an ad-hoc manual click stay
identical in behavior.
 
The $1B AUM liquidity floor is intentionally NOT applied at ingestion
time. The warehouse stores everything in the candidate universe as-is;
the AUM filter is applied at query/read time (see queries.py and
app.py) so the threshold stays adjustable in the UI without needing to
re-ingest.
"""
 
from __future__ import annotations
import argparse
import sys
import uuid
import datetime as dt
from pathlib import Path
 
# Make the repo root importable regardless of how this module is invoked
# (python warehouse/ingest.py, python -m warehouse.ingest, or imported
# from app.py) — avoids depending on the caller's working directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
 
import pandas as pd
 
from etf_universe import UNIVERSE
from data_engine import fetch_fund_info, fetch_price_history
from warehouse.connection import get_connection, schema_for
 
 
def _tickers_for_region(region: str) -> list[str]:
    return [m.ticker for m in UNIVERSE if m.region == region]
 
 
def run_ingestion(region: str, period: str = "3y", tickers: list[str] | None = None) -> dict:
    """
    Full refresh for one region: pull fund metadata + price history from
    Yahoo Finance and upsert into that region's DuckDB schema.
 
    Returns a summary dict (also written to ingestion_log).
    """
    run_id = str(uuid.uuid4())
    started_at = dt.datetime.now()
    schema = schema_for(region)
    tickers = tickers or _tickers_for_region(region)
 
    status, note = "success", ""
    tickers_loaded = 0
    price_rows_upserted = 0
 
    con = get_connection(read_only=False)
    try:
        # ---- fund metadata ----
        fund_info = fetch_fund_info(tickers)
        fund_info = fund_info.reset_index().rename(columns={"index": "ticker"})
        fund_info["region"] = region
        fund_info["last_updated"] = started_at
 
        loaded_tickers = fund_info["ticker"].tolist()
        tickers_loaded = len(loaded_tickers)
 
        con.execute(f"DELETE FROM {schema}.funds WHERE ticker IN (SELECT ticker FROM fund_info)")
        con.register("fund_info", fund_info)
        con.execute(f"""
            INSERT INTO {schema}.funds
            SELECT ticker, name, category, issuer, region, currency,
                   aum, expense_ratio, dividend_yield, last_updated
            FROM fund_info
        """)
        con.unregister("fund_info")
 
        # ---- price history ----
        prices_wide = fetch_price_history(tickers, period=period)
        if not prices_wide.empty:
            date_col = prices_wide.index.name or "index"
            prices_long = (
                prices_wide.reset_index()
                .rename(columns={date_col: "price_date"})
                .melt(id_vars=["price_date"], var_name="ticker", value_name="close")
                .dropna(subset=["close"])
            )
            prices_long["price_date"] = pd.to_datetime(prices_long["price_date"]).dt.date
 
            con.execute(f"DELETE FROM {schema}.prices WHERE ticker IN (SELECT ticker FROM prices_long)")
            con.register("prices_long", prices_long)
            con.execute(f"""
                INSERT INTO {schema}.prices
                SELECT ticker, price_date, close FROM prices_long
            """)
            con.unregister("prices_long")
            price_rows_upserted = len(prices_long)
 
        if tickers_loaded < len(tickers):
            status = "partial"
            note = f"{len(tickers) - tickers_loaded} of {len(tickers)} tickers failed to resolve."
 
    except Exception as exc:  # noqa: BLE001 — log and re-raise-free so the run record is always written
        status = "failed"
        note = str(exc)
    finally:
        finished_at = dt.datetime.now()
        con.execute(
            """
            INSERT OR REPLACE INTO main.ingestion_log
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id, region, started_at, finished_at,
                len(tickers), tickers_loaded, price_rows_upserted,
                status, note,
            ],
        )
        con.close()
 
    return {
        "run_id": run_id,
        "region": region,
        "status": status,
        "note": note,
        "tickers_requested": len(tickers),
        "tickers_loaded": tickers_loaded,
        "price_rows_upserted": price_rows_upserted,
        "started_at": started_at,
        "finished_at": finished_at,
    }
 
 
def run_full_refresh(period: str = "3y") -> list[dict]:
    """Convenience wrapper: refresh both US and Canada schemas."""
    return [run_ingestion(region, period=period) for region in ("US", "Canada")]
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load ETF data into the DuckDB warehouse.")
    parser.add_argument("--region", choices=["US", "Canada", "both"], default="both")
    parser.add_argument("--period", default="3y", help="yfinance period, e.g. 1y/2y/3y/5y")
    args = parser.parse_args()
 
    regions = ["US", "Canada"] if args.region == "both" else [args.region]
    for r in regions:
        summary = run_ingestion(r, period=args.period)
        print(
            f"[{summary['status'].upper()}] {r}: "
            f"{summary['tickers_loaded']}/{summary['tickers_requested']} tickers, "
            f"{summary['price_rows_upserted']} price rows. {summary['note']}"
        )