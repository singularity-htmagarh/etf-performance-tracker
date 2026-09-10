"""
warehouse/queries.py
----------------------
Read-only helpers the Streamlit app uses to pull data out of the
DuckDB warehouse. Returns pandas DataFrames shaped exactly like the
live-fetch functions in data_engine.py (same columns/index), so
app.py's downstream code (compute_performance_table, apply_liquidity_screen,
etc.) doesn't need to know whether the data came from Yahoo Finance
directly or from the warehouse.
"""
 
from __future__ import annotations
import pandas as pd
import duckdb
 
from warehouse.connection import get_connection, schema_for, warehouse_exists
 
 
def load_funds(region: str) -> pd.DataFrame:
    """
    Fund metadata for one region, indexed by ticker — same shape as
    data_engine.fetch_fund_info().
    """
    if not warehouse_exists():
        return pd.DataFrame()
    schema = schema_for(region)
    con = get_connection(read_only=True)
    try:
        df = con.execute(f"SELECT * FROM {schema}.funds").fetchdf()
    finally:
        con.close()
    if df.empty:
        return df
    return df.set_index("ticker")
 
 
def load_funds_multi(regions: list[str]) -> pd.DataFrame:
    """Fund metadata across multiple regions, concatenated."""
    frames = [load_funds(r) for r in regions]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames)
 
 
def load_prices(region: str, tickers: list[str] | None = None) -> pd.DataFrame:
    """
    Daily close prices for one region, pivoted wide — same shape as
    data_engine.fetch_price_history(): index = date, columns = ticker.
    """
    if not warehouse_exists():
        return pd.DataFrame()
    schema = schema_for(region)
    con = get_connection(read_only=True)
    try:
        if tickers:
            placeholders = ", ".join(["?"] * len(tickers))
            query = f"""
                SELECT price_date, ticker, close
                FROM {schema}.prices
                WHERE ticker IN ({placeholders})
                ORDER BY price_date
            """
            long_df = con.execute(query, tickers).fetchdf()
        else:
            long_df = con.execute(
                f"SELECT price_date, ticker, close FROM {schema}.prices ORDER BY price_date"
            ).fetchdf()
    finally:
        con.close()
 
    if long_df.empty:
        return pd.DataFrame()
 
    wide = long_df.pivot(index="price_date", columns="ticker", values="close")
    wide.index = pd.to_datetime(wide.index)
    wide.index.name = None
    return wide
 
 
def load_prices_multi(regions: list[str], tickers: list[str] | None = None) -> pd.DataFrame:
    """Prices across multiple regions, joined on date into one wide frame."""
    frames = [load_prices(r, tickers=tickers) for r in regions]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.join(f, how="outer")
    return out
 
 
def get_last_ingestion(region: str | None = None) -> pd.DataFrame:
    """Most recent ingestion_log row(s). Pass region=None for all regions."""
    if not warehouse_exists():
        return pd.DataFrame()
    con = get_connection(read_only=True)
    try:
        if region:
            df = con.execute(
                """
                SELECT * FROM main.ingestion_log
                WHERE region = ?
                ORDER BY finished_at DESC
                LIMIT 1
                """,
                [region],
            ).fetchdf()
        else:
            df = con.execute(
                """
                SELECT * FROM main.ingestion_log
                QUALIFY ROW_NUMBER() OVER (PARTITION BY region ORDER BY finished_at DESC) = 1
                """
            ).fetchdf()
    finally:
        con.close()
    return df
 
 
def warehouse_is_populated(region: str) -> bool:
    """True if the warehouse file exists and the region schema has at least one fund row."""
    if not warehouse_exists():
        return False
    schema = schema_for(region)
    con = get_connection(read_only=True)
    try:
        n = con.execute(f"SELECT COUNT(*) FROM {schema}.funds").fetchone()[0]
    except duckdb.CatalogException:
        n = 0
    finally:
        con.close()
    return n > 0