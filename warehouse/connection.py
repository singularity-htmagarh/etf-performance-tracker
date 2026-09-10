"""
warehouse/connection.py
------------------------
Connection helper for the ETF warehouse DuckDB file. Handles first-run
schema creation so every caller (ingest jobs, the Streamlit app, ad-hoc
notebooks) gets a ready-to-query database with a single function call.
"""
 
from __future__ import annotations
from pathlib import Path
import duckdb
 
WAREHOUSE_DIR = Path(__file__).resolve().parent
DB_PATH = WAREHOUSE_DIR / "etf_warehouse.duckdb"
SCHEMA_SQL_PATH = WAREHOUSE_DIR / "schema.sql"
 
REGION_SCHEMA = {
    "US": "us_etf",
    "Canada": "ca_etf",
}
 
 
def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """
    Open (and, on first use, initialize) the warehouse database.
 
    Parameters
    ----------
    read_only:
        Pass True for callers that only ever query (e.g. the Streamlit
        app's normal read path). DuckDB allows multiple concurrent
        read-only connections; use read_only=False only for ingestion
        jobs that write.
    """
    con = duckdb.connect(str(DB_PATH), read_only=read_only)
    if not read_only:
        _ensure_schema(con)
    return con
 
 
def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    ddl = SCHEMA_SQL_PATH.read_text()
    con.execute(ddl)
 
 
def schema_for(region: str) -> str:
    """Map a human-readable region ('US' / 'Canada') to its DuckDB schema name."""
    try:
        return REGION_SCHEMA[region]
    except KeyError as e:
        raise ValueError(f"Unknown region {region!r}. Expected one of {list(REGION_SCHEMA)}") from e
 
 
def warehouse_exists() -> bool:
    return DB_PATH.exists()