-- schema.sql
-- ----------------------------------------------------------------------
-- DuckDB warehouse schema for the ETF Performance Tracker.
--
-- Data is kept in two fully separate schemas so US and Canada ETF
-- data never mix, per Heath's requirement:
--   us_etf.*      -- US-listed ETFs
--   ca_etf.*      -- Canada (TSX)-listed ETFs
--
-- Each region schema has the same two tables:
--   funds   -- one row per ticker, fund-level metadata (AUM, expense
--             ratio, etc.) that gets overwritten on each ingestion run
--   prices  -- one row per (ticker, date), daily adjusted close
--
-- A single shared `ingestion_log` table (default/main schema) tracks
-- every ingestion run across both regions for auditability.
-- ----------------------------------------------------------------------
 
CREATE SCHEMA IF NOT EXISTS us_etf;
CREATE SCHEMA IF NOT EXISTS ca_etf;
 
-- ---------------- US ----------------
CREATE TABLE IF NOT EXISTS us_etf.funds (
    ticker          VARCHAR PRIMARY KEY,
    name            VARCHAR,
    category        VARCHAR,
    issuer          VARCHAR,
    region          VARCHAR,
    currency        VARCHAR,
    aum             DOUBLE,
    expense_ratio   DOUBLE,
    dividend_yield  DOUBLE,
    last_updated    TIMESTAMP
);
 
CREATE TABLE IF NOT EXISTS us_etf.prices (
    ticker      VARCHAR,
    price_date  DATE,
    close       DOUBLE,
    PRIMARY KEY (ticker, price_date)
);
 
-- ---------------- Canada ----------------
CREATE TABLE IF NOT EXISTS ca_etf.funds (
    ticker          VARCHAR PRIMARY KEY,
    name            VARCHAR,
    category        VARCHAR,
    issuer          VARCHAR,
    region          VARCHAR,
    currency        VARCHAR,
    aum             DOUBLE,
    expense_ratio   DOUBLE,
    dividend_yield  DOUBLE,
    last_updated    TIMESTAMP
);
 
CREATE TABLE IF NOT EXISTS ca_etf.prices (
    ticker      VARCHAR,
    price_date  DATE,
    close       DOUBLE,
    PRIMARY KEY (ticker, price_date)
);
 
-- ---------------- Shared: ingestion audit log ----------------
CREATE TABLE IF NOT EXISTS main.ingestion_log (
    run_id                  VARCHAR PRIMARY KEY,
    region                  VARCHAR,
    started_at              TIMESTAMP,
    finished_at             TIMESTAMP,
    tickers_requested       INTEGER,
    tickers_loaded          INTEGER,
    price_rows_upserted     INTEGER,
    status                  VARCHAR,   -- 'success' | 'partial' | 'failed'
    note                    VARCHAR
);