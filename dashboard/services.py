"""Dashboard data preparation; calculation logic remains in data_engine."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.core.cache import cache

from data_engine import MIN_AUM, apply_liquidity_screen, compute_performance_table
from etf_universe import META_BY_TICKER
from warehouse.queries import (
    get_last_ingestion,
    load_funds_multi,
    load_prices_multi,
    warehouse_is_populated,
)

REGIONS = ("US", "Canada")
PERIODS = ("1y", "2y", "3y", "5y")
BENCHMARKS = ("SPY", "VTI", "XIC.TO", "ACWI")
SORT_COLUMNS = (
    "aum", "1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "Sharpe_1Y", "Vol_1Y_Ann",
)
DISPLAY_COLUMNS = (
    "name", "region", "category", "issuer", "aum", "expense_ratio", "Last_Price",
    "1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "Vol_1Y_Ann",
    "Sharpe_1Y", "MaxDD_1Y", "Beta_1Y",
)
PERCENT_COLUMNS = {
    "1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "Vol_1Y_Ann",
    "MaxDD_1Y", "MaxDD_3Y", "expense_ratio",
}


def _cached_funds(regions: tuple[str, ...]) -> pd.DataFrame:
    return cache.get_or_set(
        f"funds:{','.join(regions)}", lambda: load_funds_multi(list(regions)), timeout=900
    )


def _cached_prices(regions: tuple[str, ...]) -> pd.DataFrame:
    return cache.get_or_set(
        f"prices:{','.join(regions)}", lambda: load_prices_multi(list(regions)), timeout=900
    )


def _plot_json(figure: go.Figure) -> dict[str, Any]:
    return json.loads(figure.to_json())


def _display(value: Any, column: str) -> str:
    if pd.isna(value):
        return "—"
    if column in PERCENT_COLUMNS:
        return f"{value:+.2%}" if column != "expense_ratio" else f"{value:.2%}"
    if column == "aum":
        return f"${value:,.0f}"
    if column == "Last_Price":
        return f"{value:,.2f}"
    if column in {"Sharpe_1Y", "Beta_1Y"}:
        return f"{value:.2f}"
    return str(value)


def _last_sync_status() -> list[dict[str, str]]:
    result = []
    for region in REGIONS:
        last = get_last_ingestion(region=region)
        if last.empty:
            result.append({"region": region, "status": "Never synced", "synced": ""})
            continue
        row = last.iloc[0]
        timestamp = pd.to_datetime(row["finished_at"]).strftime("%Y-%m-%d %H:%M")
        result.append({
            "region": region,
            "status": f"{row['tickers_loaded']} ETFs · {row['status']}",
            "synced": timestamp,
        })
    return result


def build_dashboard_context(params: Any) -> dict[str, Any]:
    """Validate request filters, load cached warehouse data, and prepare page data."""
    regions = tuple(region for region in params.getlist("region") if region in REGIONS)
    if not params.get("regions_present"):
        regions = REGIONS
    min_aum_b = _bounded_float(params.get("min_aum"), 1.0, 1.0, 50.0)
    period = params.get("period") if params.get("period") in PERIODS else "3y"
    benchmark = params.get("benchmark") if params.get("benchmark") in BENCHMARKS else "SPY"
    active_tab = params.get("tab", "overview")
    valid_tabs = {"overview", "table", "charts", "correlation", "detail"}
    if active_tab not in valid_tabs:
        active_tab = "overview"

    context: dict[str, Any] = {
        "regions": regions,
        "region_options": REGIONS,
        "regions_present": True,
        "min_aum_b": min_aum_b,
        "period": period,
        "period_options": PERIODS,
        "benchmark": benchmark,
        "benchmark_options": BENCHMARKS,
        "active_tab": active_tab,
        "last_sync": _last_sync_status(),
        "min_aum_default": MIN_AUM / 1e9,
        "has_data": False,
        "global_params": _global_params(regions, min_aum_b, period, benchmark),
    }

    if not regions:
        context["empty_message"] = "Select at least one region in the filters."
        return context

    unpopulated = [region for region in regions if not warehouse_is_populated(region)]
    if unpopulated:
        context["unpopulated"] = unpopulated
        context["empty_message"] = (
            f"The warehouse has no data yet for: {', '.join(unpopulated)}. "
            "Run the initial sync to populate it."
        )
        return context

    fund_info = _cached_funds(regions)
    screened = apply_liquidity_screen(fund_info, min_aum=min_aum_b * 1e9)
    if screened.empty:
        context["empty_message"] = "No ETFs passed the selected AUM and region filters."
        return context

    prices = _cached_prices(regions)
    prices = prices[[ticker for ticker in screened.index if ticker in prices.columns]]
    if benchmark not in prices.columns:
        benchmark_region = META_BY_TICKER[benchmark].region if benchmark in META_BY_TICKER else "US"
        if warehouse_is_populated(benchmark_region):
            benchmark_prices = _cached_prices((benchmark_region,))
            if benchmark in benchmark_prices.columns:
                prices = prices.join(benchmark_prices[[benchmark]], how="outer")

    if prices.empty or not any(ticker in prices.columns for ticker in screened.index):
        context["empty_message"] = "No price history is available for the ETFs in this view."
        return context

    performance = compute_performance_table(prices, screened, benchmark=benchmark)
    if performance.empty:
        context["empty_message"] = "No price history is available for the ETFs in this view."
        return context
    performance = performance.sort_values("aum", ascending=False)

    context.update(_performance_context(performance, prices, params, benchmark, period, regions))
    context["has_data"] = True
    return context


def _bounded_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        return min(high, max(low, float(value)))
    except (TypeError, ValueError):
        return default


def _global_params(regions: tuple[str, ...], min_aum: float, period: str, benchmark: str) -> list[tuple[str, str]]:
    values = [("regions_present", "1"), ("min_aum", str(min_aum)), ("period", period), ("benchmark", benchmark)]
    values.extend(("region", region) for region in regions)
    return values


def _performance_context(
    performance: pd.DataFrame,
    prices: pd.DataFrame,
    params: Any,
    benchmark: str,
    period: str,
    regions: tuple[str, ...],
) -> dict[str, Any]:
    categories = sorted(performance["category"].dropna().unique().tolist())
    category_values = [category for category in params.getlist("category") if category in categories]
    sort_column = params.get("sort", "aum")
    if sort_column not in SORT_COLUMNS:
        sort_column = "aum"
    try:
        requested_top_n = int(params.get("top_n", min(25, len(performance))))
    except (TypeError, ValueError):
        requested_top_n = min(25, len(performance))
    top_n = min(len(performance), max(5, requested_top_n))

    table = performance.copy()
    if category_values:
        table = table[table["category"].isin(category_values)]
    table = table.sort_values(sort_column, ascending=False).head(top_n)
    display_columns = [column for column in DISPLAY_COLUMNS if column in table.columns]
    table_rows = []
    for ticker, row in table[display_columns].iterrows():
        table_rows.append({
            "ticker": ticker,
            "cells": [_display(row[column], column) for column in display_columns],
        })

    selected_for_compare = [ticker for ticker in params.getlist("compare") if ticker in performance.index]
    if not params.get("compare_present"):
        selected_for_compare = performance.head(5).index.tolist()
    correlation_tickers = [ticker for ticker in params.getlist("correlation_ticker") if ticker in performance.index]
    if not params.get("correlation_present"):
        correlation_tickers = performance.head(15).index.tolist()
    selected_ticker = params.get("ticker", "")
    if selected_ticker not in performance.index:
        selected_ticker = performance.index[0]

    best = performance["1D"].idxmax() if performance["1D"].notna().any() else None
    worst = performance["1D"].idxmin() if performance["1D"].notna().any() else None
    avg_ytd = performance["YTD"].mean()

    category_performance = performance.assign(weighted_1m=performance["1M"] * performance["aum"])
    category_performance = category_performance.groupby("category").agg(
        weighted_1m=("weighted_1m", "sum"), total_aum=("aum", "sum")
    )
    category_performance["aum_wtd_1m"] = (
        category_performance["weighted_1m"] / category_performance["total_aum"].replace(0, np.nan)
    )
    category_performance = category_performance[["aum_wtd_1m"]].reset_index().sort_values("aum_wtd_1m")
    category_chart = px.bar(
        category_performance, x="aum_wtd_1m", y="category", orientation="h",
        color="aum_wtd_1m", color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
        labels={"aum_wtd_1m": "AUM-weighted 1M return", "category": ""},
    )
    category_chart.update_layout(coloraxis_showscale=False, height=520, xaxis_tickformat=".1%")

    issuer_aum = performance.groupby("issuer")["aum"].sum().sort_values(ascending=False).reset_index()
    issuer_chart = px.treemap(issuer_aum, path=["issuer"], values="aum", color="aum", color_continuous_scale="Blues")
    issuer_chart.update_layout(height=380, margin=dict(t=10, l=10, r=10, b=10))

    movers = performance[["name", "region", "1D"]].dropna().sort_values("1D", ascending=False)
    detail = performance.loc[selected_ticker]
    detail_history = prices[selected_ticker].dropna() if selected_ticker in prices.columns else pd.Series(dtype=float)

    return {
        "has_data": True,
        "performance_count": len(performance),
        "total_aum": f"${performance['aum'].sum() / 1e9:,.0f}B",
        "best_ticker": best or "—",
        "best_return": _display(performance.loc[best, "1D"], "1D") if best else "—",
        "worst_ticker": worst or "—",
        "worst_return": _display(performance.loc[worst, "1D"], "1D") if worst else "—",
        "average_ytd": _display(avg_ytd, "YTD"),
        "region_count": performance["region"].nunique(),
        "category_count": performance["category"].nunique(),
        "categories": categories,
        "selected_categories": category_values,
        "sort_column": sort_column,
        "sort_columns": SORT_COLUMNS,
        "top_n": top_n,
        "table_columns": display_columns,
        "table_rows": table_rows,
        "table_csv": table[display_columns].to_csv(index=True, index_label="ticker"),
        "gainers": _mover_rows(movers.head(5)),
        "decliners": _mover_rows(movers.tail(5).sort_values("1D")),
        "category_chart": _plot_json(category_chart),
        "issuer_chart": _plot_json(issuer_chart),
        "ticker_options": [
            {"ticker": ticker, "name": row["name"]}
            for ticker, row in performance[["name"]].iterrows()
        ],
        "selected_compare": selected_for_compare,
        "selected_correlation": correlation_tickers,
        "selected_ticker": selected_ticker,
        "detail": _detail_context(detail, selected_ticker, benchmark, period, detail_history),
        "comparison_chart": _comparison_chart(prices, selected_for_compare),
        "correlation_chart": _correlation_chart(prices, correlation_tickers),
        "global_params": _global_params(regions, _bounded_float(params.get("min_aum"), 1.0, 1.0, 50.0), period, benchmark),
        "benchmark": benchmark,
        "period": period,
        "min_aum_default": MIN_AUM / 1e9,
    }


def _mover_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
    return [
        {"ticker": ticker, "name": row["name"], "return": _display(row["1D"], "1D")}
        for ticker, row in frame.iterrows()
    ]


def _comparison_chart(prices: pd.DataFrame, tickers: list[str]) -> dict[str, Any] | None:
    available = [ticker for ticker in tickers if ticker in prices.columns]
    if not available:
        return None
    normalized = prices[available].dropna(how="all")
    normalized = normalized / normalized.bfill().iloc[0] * 100
    figure = go.Figure()
    for ticker in available:
        figure.add_trace(go.Scatter(x=normalized.index, y=normalized[ticker], mode="lines", name=ticker))
    figure.update_layout(
        height=480, yaxis_title="Indexed to 100", xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return _plot_json(figure)


def _correlation_chart(prices: pd.DataFrame, tickers: list[str]) -> dict[str, Any] | None:
    available = [ticker for ticker in tickers if ticker in prices.columns]
    if len(available) < 2:
        return None
    returns = prices[available].pct_change().dropna(how="all")
    figure = px.imshow(
        returns.corr(), text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto"
    )
    figure.update_layout(height=600)
    return _plot_json(figure)


def _detail_context(
    row: pd.Series,
    ticker: str,
    benchmark: str,
    period: str,
    history: pd.Series,
) -> dict[str, Any]:
    figure = go.Figure()
    if not history.empty:
        figure.add_trace(go.Scatter(x=history.index, y=history.values, mode="lines", name=ticker, line=dict(width=2)))
    figure.update_layout(height=420, title=f"{ticker} — price history ({period})", yaxis_title="Price")
    risk_snapshot = (
        f"1Y annualized volatility {_display(row['Vol_1Y_Ann'], 'Vol_1Y_Ann')} · "
        f"1Y max drawdown {_display(row['MaxDD_1Y'], 'MaxDD_1Y')} · "
        f"3Y max drawdown {_display(row['MaxDD_3Y'], 'MaxDD_3Y')} · "
        f"Beta vs {benchmark}: {_display(row['Beta_1Y'], 'Beta_1Y')}"
        if pd.notna(row["Beta_1Y"]) else "Beta unavailable for this window."
    )
    return {
        "ticker": ticker,
        "name": row["name"],
        "last_price": _display(row["Last_Price"], "Last_Price"),
        "aum": f"${row['aum'] / 1e9:,.2f}B" if pd.notna(row["aum"]) else "—",
        "expense_ratio": _display(row["expense_ratio"], "expense_ratio"),
        "sharpe": _display(row["Sharpe_1Y"], "Sharpe_1Y"),
        "returns": [{"label": label, "value": _display(row[label], label)} for label in ("1D", "1W", "1M", "3M", "6M", "YTD", "1Y")],
        "category": row["category"],
        "region": row["region"],
        "issuer": row["issuer"],
        "risk_snapshot": risk_snapshot,
        "chart": _plot_json(figure),
    }