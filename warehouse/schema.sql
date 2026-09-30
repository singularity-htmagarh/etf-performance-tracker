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
--   prices  -- one row per (ticker, date), adjusted OHLC and indicators
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
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE,
    ema_50      DOUBLE,
    ema_200     DOUBLE,
    ema_spread  DOUBLE,
    ema_spread_pct DOUBLE,
    rsi_14      DOUBLE,
    rsi_signal  VARCHAR,
    atr_14      DOUBLE,
    atr_pct     DOUBLE,
    volatility_regime VARCHAR,
    trend_signal VARCHAR,
    PRIMARY KEY (ticker, price_date)
);

ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS high DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS low DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS ema_50 DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS ema_200 DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS ema_spread DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS ema_spread_pct DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS rsi_14 DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS rsi_signal VARCHAR;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS atr_14 DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS atr_pct DOUBLE;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS volatility_regime VARCHAR;
ALTER TABLE us_etf.prices ADD COLUMN IF NOT EXISTS trend_signal VARCHAR;
 
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
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE,
    ema_50      DOUBLE,
    ema_200     DOUBLE,
    ema_spread  DOUBLE,
    ema_spread_pct DOUBLE,
    rsi_14      DOUBLE,
    rsi_signal  VARCHAR,
    atr_14      DOUBLE,
    atr_pct     DOUBLE,
    volatility_regime VARCHAR,
    trend_signal VARCHAR,
    PRIMARY KEY (ticker, price_date)
);

ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS high DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS low DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS ema_50 DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS ema_200 DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS ema_spread DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS ema_spread_pct DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS rsi_14 DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS rsi_signal VARCHAR;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS atr_14 DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS atr_pct DOUBLE;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS volatility_regime VARCHAR;
ALTER TABLE ca_etf.prices ADD COLUMN IF NOT EXISTS trend_signal VARCHAR;
 
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