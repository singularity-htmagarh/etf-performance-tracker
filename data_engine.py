"""
data_engine.py
---------------
Data acquisition and performance-metrics computation for the ETF tracker.
All external calls go through yfinance. Everything here is cached at the
Streamlit layer (app.py) via st.cache_data — this module stays a plain,
testable library with no Streamlit dependency.
"""
 
from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf
 
from etf_universe import ALL_TICKERS, META_BY_TICKER
 
TRADING_DAYS_YEAR = 252
RISK_FREE_RATE_ANNUAL = 0.045  # proxy — update to current T-bill / CORRA rate as needed
MIN_AUM = 1_000_000_000  # $1B liquidity floor
 
 
# --------------------------------------------------------------------------
# Raw data pulls
# --------------------------------------------------------------------------
 
def fetch_fund_info(tickers: list[str]) -> pd.DataFrame:
    """
    Pull static/slow-changing fund metadata (AUM, expense ratio, yield,
    category) for each ticker via yfinance.Ticker.info. This is the
    field used to enforce the AUM > $1B liquidity screen.
 
    Returns a DataFrame indexed by ticker. Tickers that fail to resolve
    (delisted, rate-limited, etc.) come back with NaNs rather than
    raising, so one bad symbol never breaks the whole screen.
    """
    rows = []
    for t in tickers:
        meta = META_BY_TICKER.get(t)
        row = {
            "ticker": t,
            "name": meta.name if meta else t,
            "region": meta.region if meta else "Unknown",
            "category": meta.category if meta else "Unknown",
            "issuer": meta.issuer if meta else "Unknown",
            "aum": np.nan,
            "expense_ratio": np.nan,
            "dividend_yield": np.nan,
            "currency": np.nan,
        }
        try:
            info = yf.Ticker(t).get_info()
            row["aum"] = info.get("totalAssets", np.nan)
            # yfinance reports these as decimals (e.g. 0.03 == 3bps... actually 3%)
            er = info.get("netExpenseRatio") or info.get("annualReportExpenseRatio")
            row["expense_ratio"] = er if er is not None else np.nan
            row["dividend_yield"] = info.get("yield", np.nan)
            row["currency"] = info.get("currency", np.nan)
            if not meta:
                row["name"] = info.get("longName") or info.get("shortName") or t
        except Exception:
            pass
        rows.append(row)
    return pd.DataFrame(rows).set_index("ticker")
 
 
def fetch_price_history(tickers: list[str], period: str = "3y") -> pd.DataFrame:
    """
    Bulk-download adjusted close prices for all tickers in one call
    (far cheaper than one call per ticker). Returns a wide DataFrame:
    index = date, columns = ticker.
    """
    if not tickers:
        return pd.DataFrame()
 
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )
 
    if raw.empty:
        return pd.DataFrame()
 
    if isinstance(raw.columns, pd.MultiIndex):
        closes = {}
        for t in tickers:
            try:
                closes[t] = raw[t]["Close"]
            except (KeyError, TypeError):
                continue
        prices = pd.DataFrame(closes)
    else:
        # single-ticker download shape
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})
 
    return prices.dropna(how="all")
 
 
# --------------------------------------------------------------------------
# Performance metrics
# --------------------------------------------------------------------------
 
def _trailing_return(series: pd.Series, n_days: int) -> float:
    s = series.dropna()
    if len(s) <= n_days:
        return np.nan
    return s.iloc[-1] / s.iloc[-1 - n_days] - 1.0
 
 
def _ytd_return(series: pd.Series) -> float:
    s = series.dropna()
    if s.empty:
        return np.nan
    this_year = s[s.index.year == s.index[-1].year]
    if this_year.empty:
        return np.nan
    # anchor to prior trading day's close if available (proper YTD basis)
    start_pos = s.index.get_loc(this_year.index[0])
    base = s.iloc[start_pos - 1] if start_pos > 0 else this_year.iloc[0]
    return s.iloc[-1] / base - 1.0
 
 
def _annualized_vol(returns: pd.Series, window: int) -> float:
    r = returns.dropna().tail(window)
    if len(r) < max(5, window // 4):
        return np.nan
    return r.std() * np.sqrt(TRADING_DAYS_YEAR)
 
 
def _sharpe(returns: pd.Series, window: int) -> float:
    r = returns.dropna().tail(window)
    if len(r) < max(5, window // 4):
        return np.nan
    excess = r - (RISK_FREE_RATE_ANNUAL / TRADING_DAYS_YEAR)
    vol = excess.std()
    if vol == 0 or np.isnan(vol):
        return np.nan
    return (excess.mean() / vol) * np.sqrt(TRADING_DAYS_YEAR)
 
 
def _max_drawdown(series: pd.Series, window: int | None = None) -> float:
    s = series.dropna()
    if window:
        s = s.tail(window)
    if s.empty:
        return np.nan
    running_max = s.cummax()
    dd = s / running_max - 1.0
    return dd.min()
 
 
def _beta(returns: pd.Series, bench_returns: pd.Series, window: int = 252) -> float:
    r = returns.tail(window)
    b = bench_returns.tail(window)
    joined = pd.concat([r, b], axis=1).dropna()
    if len(joined) < 30:
        return np.nan
    cov = joined.cov().iloc[0, 1]
    var = joined.iloc[:, 1].var()
    if var == 0 or np.isnan(var):
        return np.nan
    return cov / var
 
 
def compute_performance_table(
    prices: pd.DataFrame,
    fund_info: pd.DataFrame,
    benchmark: str = "SPY",
) -> pd.DataFrame:
    """
    Build the core performance/risk table: one row per ETF, columns for
    every horizon and risk statistic the dashboard displays.
    """
    daily_returns = prices.pct_change()
    bench_returns = daily_returns[benchmark] if benchmark in daily_returns.columns else None
 
    records = []
    for t in prices.columns:
        s = prices[t].dropna()
        if s.empty:
            continue
        r = daily_returns[t]
 
        rec = {
            "ticker": t,
            "1D": _trailing_return(s, 1),
            "1W": _trailing_return(s, 5),
            "1M": _trailing_return(s, 21),
            "3M": _trailing_return(s, 63),
            "6M": _trailing_return(s, 126),
            "YTD": _ytd_return(s),
            "1Y": _trailing_return(s, 252),
            "3Y": _trailing_return(s, 756),
            "Vol_1Y_Ann": _annualized_vol(r, 252),
            "Sharpe_1Y": _sharpe(r, 252),
            "MaxDD_1Y": _max_drawdown(s, 252),
            "MaxDD_3Y": _max_drawdown(s, 756),
            "Beta_1Y": _beta(r, bench_returns, 252) if bench_returns is not None else np.nan,
            "Last_Price": s.iloc[-1],
        }
        records.append(rec)
 
    perf = pd.DataFrame(records).set_index("ticker")
    out = fund_info.join(perf, how="inner")
    return out
 
 
def apply_liquidity_screen(fund_info: pd.DataFrame, min_aum: float = MIN_AUM) -> pd.DataFrame:
    """Keep only ETFs with reported AUM above the liquidity floor."""
    screened = fund_info[fund_info["aum"] >= min_aum].copy()
    return screened.sort_values("aum", ascending=False)