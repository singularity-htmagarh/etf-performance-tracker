# ETF Performance Tracker

A Streamlit dashboard for monitoring the performance, risk, and positioning of large, liquid ETFs listed in the United States and Canada. The app uses a curated ETF universe, applies a live assets-under-management (AUM) screen, downloads market data from Yahoo Finance through `yfinance`, and calculates comparable return and risk metrics.

This project tracks ETF market performance. It does not connect to a brokerage account or calculate the performance of a user's actual holdings.

## Features

- Curated US and Canada-listed ETF universe covering broad equity, style, sector, international, fixed income, commodity, dividend, and income/options categories.
- Runtime liquidity screen based on reported AUM, with a configurable minimum from `$1B` to `$50B`.
- Region filter for US and Canada ETFs.
- Configurable price history window of 1, 2, 3, or 5 years.
- Selectable beta benchmark: `SPY`, `VTI`, `XIC.TO`, or `ACWI`.
- Cached fund metadata and price history with a force-refresh control.
- CSV export for the filtered performance table.

## Dashboard sections

The app is organized into five tabs:

1. **Market Overview**: AUM-weighted average 1-month performance by category, top daily gainers and decliners, and AUM concentration by issuer.
2. **Performance Table**: Sortable and filterable ETF table with metadata, returns, volatility, Sharpe ratio, maximum drawdown, and beta.
3. **Comparison Charts**: Normalized price performance and drawdown charts for selected ETFs.
4. **Correlation**: Return-correlation heatmap for a selected ETF subset.
5. **ETF Detail**: Price history, key fund metadata, trailing returns, and a risk snapshot for one ETF.

## Performance metrics

Returns are calculated from adjusted daily closing prices using approximate trading-day horizons:

| Metric | Calculation |
| --- | --- |
| `1D`, `1W`, `1M`, `3M`, `6M` | Trailing returns over 1, 5, 21, 63, and 126 trading days |
| `YTD` | Return from the prior trading day's close before the current calendar year |
| `1Y`, `3Y` | Trailing returns over 252 and 756 trading days |
| `Vol_1Y_Ann` | Annualized standard deviation of the latest 252 daily returns |
| `Sharpe_1Y` | Annualized excess return using a 4.5% annual risk-free-rate proxy |
| `MaxDD_1Y`, `MaxDD_3Y` | Worst peak-to-trough drawdown over the latest 252 or 756 trading days |
| `Beta_1Y` | Covariance with the selected benchmark divided by benchmark variance over the latest 252 trading days |

Metrics that do not have enough price history are shown as unavailable. The benchmark is downloaded alongside the ETF prices when it is not already in the selected universe.

## Data flow

1. `etf_universe.py` defines the candidate symbols and static labels for name, region, category, and issuer. Canadian symbols use Yahoo Finance's `.TO` suffix.
2. `data_engine.py` retrieves fund metadata and adjusted daily prices, applies the AUM screen, and builds the performance table.
3. `app.py` provides the Streamlit interface, caching, filters, charts, table styling, and CSV download.

Metadata is retrieved from `yfinance.Ticker.info`, including reported total assets, expense ratio, distribution yield, and currency. Price history is retrieved in bulk with `yfinance.download(..., auto_adjust=True)`.

## Requirements

- Python 3.10 or newer is recommended because the code uses modern type-annotation syntax.
- Network access to Yahoo Finance is required when the app loads or refreshes data.

Install the dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Run the dashboard

From the repository root:

```bash
streamlit run app.py
```

Streamlit will display a local URL, typically `http://localhost:8501`.

## Project structure

```text
.
├── app.py              # Streamlit dashboard and user controls
├── data_engine.py      # Yahoo Finance access and metric calculations
├── etf_universe.py     # Curated ETF metadata and ticker list
├── requirements.txt    # Python dependencies
└── README.md           # Project documentation
```

## Important caveats

- The candidate universe is curated in code; it is not a complete scan of every ETF.
- Inclusion is based on the latest reported `totalAssets` value available from Yahoo Finance and can change between sessions.
- AUM and expense-ratio metadata may lag the live market and issuer reporting.
- Yahoo Finance availability, rate limits, missing symbols, and incomplete histories can result in missing values.
- The Sharpe ratio uses a fixed 4.5% annual risk-free-rate proxy defined in `data_engine.py`; it is not automatically updated.
- Results are for research and monitoring only and are not investment advice.

# ETF Warehouse (DuckDB)

Local DuckDB data layer for the ETF Performance Tracker. Stores US and
Canada ETF data in **separate schemas** so the two are never mixed,
and gives the Streamlit app a fast, offline-capable read path instead
of hitting Yahoo Finance on every page load.

## Layout

```
warehouse/
  schema.sql          DDL — run automatically on first connection
  connection.py        get_connection(), schema_for(region)
  ingest.py             ETL job: Yahoo Finance -> DuckDB
  queries.py             Read helpers used by app.py
  etf_warehouse.duckdb  the actual database file (git-ignored, created on first ingest)
```

## Schema

Two schemas, identical structure, kept fully separate:

| Schema    | Region |
|-----------|--------|
| `us_etf`  | US-listed ETFs |
| `ca_etf`  | Canada (TSX)-listed ETFs (`.TO` tickers) |

Each has:

- **`funds`** — one row per ticker: name, category, issuer, currency,
  AUM, expense ratio, dividend yield, `last_updated`. Overwritten in
  full on every sync for that region.
- **`prices`** — one row per `(ticker, price_date)`: adjusted close.
  Upserted per ticker (old rows for a ticker are deleted and replaced
  with the freshly pulled range) so re-syncing is idempotent — no
  duplicate rows, no manual cleanup.

A shared `main.ingestion_log` table records every sync (region,
timing, tickers requested/loaded, price rows written, status, notes)
for auditability — same spirit as the run logging in the rest of the
personal trading infrastructure.

**Note:** the $1B AUM liquidity screen is *not* applied at ingestion
time — the warehouse stores the full candidate universe (see
`etf_universe.py`) as-is. The filter is applied at read time in
`app.py`, so moving the AUM slider in the UI doesn't require
re-ingesting.

## Usage

### First-time setup / manual refresh

```bash
# both regions, 3 years of price history (default)
python -m warehouse.ingest

# one region only
python -m warehouse.ingest --region US
python -m warehouse.ingest --region Canada

# longer history
python -m warehouse.ingest --period 5y
```

This creates `warehouse/etf_warehouse.duckdb` if it doesn't exist yet,
applies `schema.sql`, and upserts fund metadata + prices.

### From the Streamlit app

`app.py` reads from the warehouse by default via `warehouse/queries.py`.
The sidebar has a **"🔄 Sync from Yahoo Finance now"** button that
calls the same `run_ingestion()` function used by the CLI, for the
currently-selected region(s), then clears the Streamlit cache and
reruns. If a selected region has never been synced, the app tells you
and stops rather than silently showing nothing.

### Scheduling

`run_ingestion()` / `run_full_refresh()` in `ingest.py` are plain
functions with no Streamlit dependency, so they drop straight into a
Prefect flow or a scheduled GitHub Actions job the same way the rest
of the personal trading infra is orchestrated — e.g. a nightly
`python -m warehouse.ingest` after market close.

## Querying directly

```python
from warehouse.queries import load_funds, load_prices, get_last_ingestion

us_funds = load_funds("US")                 # DataFrame indexed by ticker
us_prices = load_prices("US")                # wide DataFrame, date index
spy_only = load_prices("US", tickers=["SPY"])
get_last_ingestion()                          # latest run per region
```

Or with raw SQL via `warehouse.connection.get_connection()`:

```python
from warehouse.connection import get_connection

con = get_connection(read_only=True)
con.execute("SELECT ticker, aum FROM us_etf.funds ORDER BY aum DESC LIMIT 10").fetchdf()
```

## Why not name this folder `duckdb/`?

Because a subfolder literally named `duckdb` sitting at the repo root
shadows the real `duckdb` PyPI package the moment the repo root is on
`sys.path` (which it is when you run `streamlit run app.py` from the
repo root) — every `import duckdb` anywhere in the app, including the
genuine library import inside these files, would resolve to the local
folder instead and break. `warehouse/` avoids the collision while
keeping the same "DuckDB warehouse" naming already used elsewhere in
the personal trading infra.
