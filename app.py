"""
ETF Performance Tracker — US & Canada, AUM > $1B
==================================================
Institutional-grade dashboard for tracking the performance, risk, and
positioning of the largest, most liquid US- and Canada-listed ETFs.
 
Run:
    streamlit run app.py
 
Data:
    yfinance (Yahoo Finance) — adjusted daily close prices + fund
    metadata (AUM, expense ratio, yield). AUM > $1B is enforced as a
    hard liquidity screen before anything else in the app runs.
"""
 
from __future__ import annotations
import datetime as dt
 
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
 
from etf_universe import ALL_TICKERS, META_BY_TICKER
from data_engine import (
    fetch_fund_info,
    fetch_price_history,
    compute_performance_table,
    apply_liquidity_screen,
    MIN_AUM,
)
 
# --------------------------------------------------------------------------
# Page config & style
# --------------------------------------------------------------------------
 
st.set_page_config(
    page_title="ETF Performance Tracker | US & Canada",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
CUSTOM_CSS = """
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    div[data-testid="stMetricValue"] {font-size: 1.4rem;}
    .small-note {color: #808495; font-size: 0.82rem;}
    thead tr th {background-color: #0e1117;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
 
PCT_COLS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "Vol_1Y_Ann", "MaxDD_1Y", "MaxDD_3Y"]
 
 
# --------------------------------------------------------------------------
# Cached data layer
# --------------------------------------------------------------------------
 
@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_fund_info(tickers: tuple[str, ...]) -> pd.DataFrame:
    return fetch_fund_info(list(tickers))
 
 
@st.cache_data(ttl=15 * 60, show_spinner=False)
def load_prices(tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    return fetch_price_history(list(tickers), period=period)
 
 
def style_pct(df: pd.DataFrame, cols: list[str]) -> pd.io.formats.style.Styler:
    fmt = {c: "{:+.2%}" for c in cols if c in df.columns}
    if "aum" in df.columns:
        fmt["aum"] = "${:,.0f}"
    if "Last_Price" in df.columns:
        fmt["Last_Price"] = "{:,.2f}"
    if "Sharpe_1Y" in df.columns:
        fmt["Sharpe_1Y"] = "{:.2f}"
    if "Beta_1Y" in df.columns:
        fmt["Beta_1Y"] = "{:.2f}"
    if "expense_ratio" in df.columns:
        fmt["expense_ratio"] = "{:.2%}"
 
    return_cols = [c for c in ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"] if c in df.columns]
    styler = df.style.format(fmt, na_rep="—")
    for c in return_cols:
        styler = styler.background_gradient(subset=[c], cmap="RdYlGn", vmin=-0.15, vmax=0.15)
    return styler
 
 
# --------------------------------------------------------------------------
# Sidebar — controls
# --------------------------------------------------------------------------
 
st.sidebar.title("📊 ETF Tracker Controls")
st.sidebar.caption("US & Canada liquid ETF universe")
 
with st.sidebar:
    min_aum_b = st.slider("Minimum AUM ($B)", min_value=1.0, max_value=50.0, value=1.0, step=0.5)
    period_choice = st.selectbox(
        "Price history window",
        options=["1y", "2y", "3y", "5y"],
        index=2,
        help="Longer windows are needed for 3Y return / drawdown stats.",
    )
    benchmark = st.selectbox(
        "Benchmark (for beta)",
        options=["SPY", "VTI", "XIC.TO", "ACWI"],
        index=0,
    )
    st.divider()
    region_filter = st.multiselect("Region", options=["US", "Canada"], default=["US", "Canada"])
    st.divider()
    refresh = st.button("🔄 Force refresh data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
    st.caption(f"Last loaded: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown(
        '<p class="small-note">Data: Yahoo Finance via yfinance. AUM and expense ratios '
        "are as last reported by the fund issuer and may lag the live tape by up to a day. "
        "Not investment advice.</p>",
        unsafe_allow_html=True,
    )
 
# --------------------------------------------------------------------------
# Load & screen data
# --------------------------------------------------------------------------
 
with st.spinner("Pulling fund metadata and enforcing AUM screen..."):
    fund_info_raw = load_fund_info(tuple(ALL_TICKERS))
 
screened = apply_liquidity_screen(fund_info_raw, min_aum=min_aum_b * 1e9)
screened = screened[screened["region"].isin(region_filter)] if region_filter else screened
 
if screened.empty:
    st.warning("No ETFs passed the current AUM/region filters. Loosen the filters in the sidebar.")
    st.stop()
 
tickers_in_scope = tuple(screened.index.tolist())
 
with st.spinner(f"Pulling price history for {len(tickers_in_scope)} ETFs..."):
    prices = load_prices(tickers_in_scope, period=period_choice)
 
if benchmark not in prices.columns:
    with st.spinner("Pulling benchmark series..."):
        bench_prices = load_prices((benchmark,), period=period_choice)
    prices = prices.join(bench_prices, how="outer")
 
perf = compute_performance_table(prices, screened, benchmark=benchmark)
perf = perf.sort_values("aum", ascending=False)
 
categories = sorted(perf["category"].dropna().unique().tolist())
 
# --------------------------------------------------------------------------
# Header + KPI strip
# --------------------------------------------------------------------------
 
st.title("📊 ETF Performance Tracker — US & Canada")
st.caption(
    f"Tracking **{len(perf)}** ETFs with AUM ≥ **${min_aum_b:.1f}B** "
    f"across {perf['region'].nunique()} region(s) and {perf['category'].nunique()} categories."
)
 
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("ETFs in scope", f"{len(perf)}")
k2.metric("Total AUM tracked", f"${perf['aum'].sum() / 1e9:,.0f}B")
best = perf["1D"].idxmax() if perf["1D"].notna().any() else None
worst = perf["1D"].idxmin() if perf["1D"].notna().any() else None
k3.metric("Best 1D", f"{best}", f"{perf.loc[best, '1D']:+.2%}" if best else "—")
k4.metric("Worst 1D", f"{worst}", f"{perf.loc[worst, '1D']:+.2%}" if worst else "—")
avg_ytd = perf["YTD"].mean()
k5.metric("Avg YTD return (equal-wt)", f"{avg_ytd:+.2%}" if pd.notna(avg_ytd) else "—")
 
st.divider()
 
# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
 
tab_overview, tab_table, tab_charts, tab_corr, tab_detail = st.tabs(
    ["🏁 Market Overview", "📋 Performance Table", "📈 Comparison Charts", "🔗 Correlation", "🔍 ETF Detail"]
)
 
# ---- Tab 1: Market Overview ----------------------------------------------
with tab_overview:
    col1, col2 = st.columns([1.3, 1])
 
    with col1:
        st.subheader("Category performance (avg 1M return, AUM-weighted)")
        cat_perf = (
            perf.assign(weighted_1m=perf["1M"] * perf["aum"])
            .groupby("category")
            .apply(lambda d: d["weighted_1m"].sum() / d["aum"].sum() if d["aum"].sum() else np.nan)
            .rename("aum_wtd_1m")
            .reset_index()
            .sort_values("aum_wtd_1m", ascending=True)
        )
        fig = px.bar(
            cat_perf,
            x="aum_wtd_1m",
            y="category",
            orientation="h",
            color="aum_wtd_1m",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            labels={"aum_wtd_1m": "AUM-weighted 1M return", "category": ""},
        )
        fig.update_layout(coloraxis_showscale=False, height=520, xaxis_tickformat=".1%")
        st.plotly_chart(fig, use_container_width=True)
 
    with col2:
        st.subheader("Top movers (1D)")
        movers = perf[["name", "region", "1D"]].dropna().sort_values("1D", ascending=False)
        st.markdown("**Gainers**")
        st.dataframe(
            style_pct(movers.head(5)[["name", "1D"]], ["1D"]),
            use_container_width=True,
        )
        st.markdown("**Decliners**")
        st.dataframe(
            style_pct(movers.tail(5).sort_values("1D")[["name", "1D"]], ["1D"]),
            use_container_width=True,
        )
 
    st.subheader("AUM concentration by issuer")
    issuer_aum = perf.groupby("issuer")["aum"].sum().sort_values(ascending=False).reset_index()
    fig2 = px.treemap(
        issuer_aum, path=["issuer"], values="aum",
        color="aum", color_continuous_scale="Blues",
    )
    fig2.update_layout(height=380, margin=dict(t=10, l=10, r=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)
 
# ---- Tab 2: Performance Table ---------------------------------------------
with tab_table:
    st.subheader("Full performance & risk table")
 
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        cat_sel = st.multiselect("Filter by category", options=categories, default=[])
    with fcol2:
        sort_col = st.selectbox(
            "Sort by",
            options=["aum", "1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "Sharpe_1Y", "Vol_1Y_Ann"],
            index=0,
        )
    with fcol3:
        top_n = st.number_input("Show top N", min_value=5, max_value=len(perf), value=min(25, len(perf)))
 
    view = perf.copy()
    if cat_sel:
        view = view[view["category"].isin(cat_sel)]
    view = view.sort_values(sort_col, ascending=False).head(int(top_n))
 
    display_cols = [
        "name", "region", "category", "issuer", "aum", "expense_ratio",
        "Last_Price", "1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y",
        "Vol_1Y_Ann", "Sharpe_1Y", "MaxDD_1Y", "Beta_1Y",
    ]
    display_cols = [c for c in display_cols if c in view.columns]
 
    st.dataframe(style_pct(view[display_cols], PCT_COLS), use_container_width=True, height=560)
 
    st.download_button(
        "⬇️ Download this view as CSV",
        data=view[display_cols].to_csv().encode("utf-8"),
        file_name=f"etf_performance_{dt.date.today().isoformat()}.csv",
        mime="text/csv",
    )
 
# ---- Tab 3: Comparison Charts ----------------------------------------------
with tab_charts:
    st.subheader("Normalized price performance")
    default_sel = perf.sort_values("aum", ascending=False).head(5).index.tolist()
    sel = st.multiselect(
        "Select ETFs to compare (normalized to 100 at start of window)",
        options=perf.index.tolist(),
        default=default_sel,
        format_func=lambda t: f"{t} — {META_BY_TICKER.get(t).name if t in META_BY_TICKER else t}",
    )
 
    if sel:
        norm = prices[sel].dropna(how="all")
        norm = norm / norm.bfill().iloc[0] * 100
        fig3 = go.Figure()
        for t in sel:
            fig3.add_trace(go.Scatter(x=norm.index, y=norm[t], mode="lines", name=t))
        fig3.update_layout(
            height=480, yaxis_title="Indexed to 100", xaxis_title="",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig3, use_container_width=True)
 
        st.subheader("Drawdown comparison")
        dd = norm / norm.cummax() - 1.0
        fig4 = go.Figure()
        for t in sel:
            fig4.add_trace(go.Scatter(x=dd.index, y=dd[t], mode="lines", name=t, fill="tozeroy"))
        fig4.update_layout(height=380, yaxis_title="Drawdown", yaxis_tickformat=".0%")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Select at least one ETF above to render the comparison charts.")
 
# ---- Tab 4: Correlation ----------------------------------------------------
with tab_corr:
    st.subheader("Return correlation matrix")
    corr_universe = st.multiselect(
        "ETFs to include in the correlation matrix",
        options=perf.index.tolist(),
        default=perf.sort_values("aum", ascending=False).head(15).index.tolist(),
    )
    if len(corr_universe) >= 2:
        ret = prices[corr_universe].pct_change().dropna(how="all")
        corr = ret.corr()
        fig5 = px.imshow(
            corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            aspect="auto",
        )
        fig5.update_layout(height=600)
        st.plotly_chart(fig5, use_container_width=True)
        st.caption("Diversification candidates sit toward the blue (low/negative correlation) cells.")
    else:
        st.info("Select at least two ETFs to build a correlation matrix.")
 
# ---- Tab 5: ETF Detail ------------------------------------------------------
with tab_detail:
    pick = st.selectbox(
        "Choose an ETF",
        options=perf.index.tolist(),
        format_func=lambda t: f"{t} — {perf.loc[t, 'name']}",
    )
    row = perf.loc[pick]
 
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Last price", f"{row['Last_Price']:,.2f}")
    d2.metric("AUM", f"${row['aum'] / 1e9:,.2f}B" if pd.notna(row["aum"]) else "—")
    d3.metric("Expense ratio", f"{row['expense_ratio']:.2%}" if pd.notna(row["expense_ratio"]) else "—")
    d4.metric("1Y Sharpe", f"{row['Sharpe_1Y']:.2f}" if pd.notna(row["Sharpe_1Y"]) else "—")
 
    r1, r2, r3, r4, r5, r6, r7 = st.columns(7)
    for col, label in zip([r1, r2, r3, r4, r5, r6, r7], ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y"]):
        val = row[label]
        col.metric(label, f"{val:+.2%}" if pd.notna(val) else "—")
 
    st.markdown(f"**Category:** {row['category']} &nbsp;|&nbsp; **Region:** {row['region']} "
                f"&nbsp;|&nbsp; **Issuer:** {row['issuer']}")
 
    hist = prices[pick].dropna()
    figd = go.Figure()
    figd.add_trace(go.Scatter(x=hist.index, y=hist.values, mode="lines", name=pick, line=dict(width=2)))
    figd.update_layout(height=420, title=f"{pick} — price history ({period_choice})")
    st.plotly_chart(figd, use_container_width=True)
 
    st.markdown(
        f"**Risk snapshot:** 1Y annualized volatility "
        f"{row['Vol_1Y_Ann']:.2%} &nbsp;|&nbsp; 1Y max drawdown {row['MaxDD_1Y']:.2%} "
        f"&nbsp;|&nbsp; 3Y max drawdown {row['MaxDD_3Y']:.2%} &nbsp;|&nbsp; "
        f"Beta vs {benchmark}: {row['Beta_1Y']:.2f}"
        if pd.notna(row["Beta_1Y"]) else "Beta unavailable for this window."
    )
 
st.divider()
st.caption(
    "Built for institutional/trading desk use. Universe is curated from the largest US- and "
    "Canada-listed ETFs by issuer; inclusion each session is gated on live AUM ≥ selected floor "
    f"(default ${MIN_AUM/1e9:.0f}B). Prices are Yahoo Finance adjusted closes; metadata (AUM, "
    "expense ratio) reflects each issuer's last filing to Yahoo Finance and can lag intraday."
)