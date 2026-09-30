from unittest.mock import patch

import numpy as np
import pandas as pd
from django.test import TestCase


class DashboardViewTests(TestCase):
    @patch("dashboard.services.get_last_ingestion")
    @patch("dashboard.services.warehouse_is_populated", return_value=False)
    def test_home_page_explains_empty_warehouse(self, _populated, last_ingestion):
        import pandas as pd

        last_ingestion.return_value = pd.DataFrame()
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The warehouse has no data yet")
        self.assertContains(response, "Sync selected region(s)")

    def test_filters_reject_unknown_values(self):
        from dashboard.services import build_dashboard_context

        with patch("dashboard.services.get_last_ingestion", return_value=pd.DataFrame()):
            context = build_dashboard_context(
                _QueryParams({"tab": "table", "region": ["Mars"], "regions_present": ["1"]})
            )

        self.assertEqual(context["regions"], ())
        self.assertEqual(context["active_tab"], "table")

    def test_us_overview_is_scoped_to_us_even_when_canada_is_requested(self):
        from dashboard.services import build_dashboard_context

        with patch("dashboard.services.get_last_ingestion", return_value=pd.DataFrame()):
            context = build_dashboard_context(
                _QueryParams({"tab": "overview", "region": ["Canada"], "regions_present": ["1"]})
            )

        self.assertEqual(context["regions"], ("US",))
        self.assertEqual(context["sector_region"], "US")
        self.assertEqual(context["page_title"], "Market Overview - US")
        self.assertEqual([item["region"] for item in context["last_sync"]], ["US"])

    def test_technical_signals_tab_renders_daily_snapshot(self):
        from datetime import date

        signal_frame = pd.DataFrame(
            [{
                "price_date": pd.Timestamp("2026-09-30"), "close": 500.0,
                "ema_50": 498.0, "ema_200": 490.0, "ema_spread": 8.0,
                "ema_spread_pct": 8 / 490, "rsi_14": 72.0, "rsi_signal": "Overbought",
                "atr_14": 5.0, "atr_pct": 0.01, "volatility_regime": "High Volatility",
                "trend_signal": "Extended Uptrend",
            }],
            index=pd.Index(["SPY"], name="ticker"),
        )
        fund_frame = pd.DataFrame(
            {"name": ["SPDR S&P 500 ETF Trust"], "region": ["US"], "category": ["US Broad Equity"]},
            index=pd.Index(["SPY"], name="ticker"),
        )
        with (
            patch("dashboard.services.get_last_ingestion", return_value=pd.DataFrame()),
            patch("dashboard.services.warehouse_is_populated", return_value=True),
            patch("dashboard.services._cached_funds", return_value=fund_frame),
            patch("dashboard.services.load_signal_dates_multi", return_value=["2026-09-30"]),
            patch("dashboard.services.load_signals_multi", return_value=signal_frame) as load_signals,
        ):
            response = self.client.get("/?tab=signals&region=US&regions_present=1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Technical signals")
        self.assertContains(response, "Overbought")
        self.assertContains(response, "High Volatility")
        self.assertContains(response, "Extended Uptrend")
        load_signals.assert_called_once_with(["US"], as_of_date=date(2026, 9, 30))

    @patch("dashboard.services.get_last_ingestion", return_value=pd.DataFrame())
    @patch("dashboard.services._cached_prices", return_value=pd.DataFrame())
    @patch("dashboard.services._cached_funds")
    @patch("dashboard.services.warehouse_is_populated", return_value=True)
    def test_populated_warehouse_without_prices_shows_empty_state(
        self, _populated, cached_funds, _cached_prices, _last_ingestion
    ):
        from dashboard.services import build_dashboard_context

        cached_funds.return_value = pd.DataFrame(
            {"aum": [2_000_000_000]}, index=pd.Index(["SPY"], name="ticker")
        )
        context = build_dashboard_context(_QueryParams({}))

        self.assertFalse(context["has_data"])
        self.assertIn("No price history is available", context["empty_message"])

    @patch("dashboard.services.get_last_ingestion", return_value=pd.DataFrame())
    @patch("dashboard.services._cached_prices")
    @patch("dashboard.services._cached_funds")
    @patch("dashboard.services.warehouse_is_populated", return_value=True)
    def test_populated_table_and_csv_use_warehouse_data(
        self, _populated, cached_funds, cached_prices, _last_ingestion
    ):
        dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=800)
        drift = np.arange(len(dates))
        funds = pd.DataFrame(
            {
                "name": ["SPDR S&P 500 ETF Trust", "Vanguard Total Stock Market ETF"],
                "region": ["US", "US"],
                "category": ["US Broad Equity", "US Broad Equity"],
                "issuer": ["State Street", "Vanguard"],
                "aum": [500_000_000_000, 400_000_000_000],
                "expense_ratio": [0.0009, 0.0003],
                "dividend_yield": [0.013, 0.014],
                "currency": ["USD", "USD"],
            },
            index=pd.Index(["SPY", "VTI"], name="ticker"),
        )
        prices = pd.DataFrame(
            {
                "SPY": 100 * np.cumprod(1 + 0.0003 + np.sin(drift / 17) * 0.001),
                "VTI": 90 * np.cumprod(1 + 0.00035 + np.sin(drift / 19) * 0.001),
            },
            index=dates,
        )
        cached_funds.return_value = funds
        cached_prices.return_value = prices

        response = self.client.get("/?tab=table")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SPDR S&amp;P 500 ETF Trust")
        self.assertContains(response, "Full performance &amp; risk table")

        csv_response = self.client.get("/?tab=table&download=csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("SPY", csv_response.content.decode("utf-8"))

    def test_sector_signal_watchlist_includes_us_gics_proxies(self):
        from etf_universe import UNIVERSE

        tickers = {meta.ticker for meta in UNIVERSE if meta.region == "US"}
        required = {"XLK", "XLF", "XLY", "XLV", "XLI", "XLU", "XLE", "XLP", "GDX", "VNQ", "VOX"}

        self.assertTrue(required.issubset(tickers))

        from dashboard.services import US_SECTOR_ETFS

        self.assertTrue(set(US_SECTOR_ETFS).issubset(tickers))

    def test_canada_sector_watchlist_includes_requested_gics_proxies(self):
        from dashboard.services import CANADA_SECTOR_ETFS
        from etf_universe import UNIVERSE

        canadian_tickers = {meta.ticker for meta in UNIVERSE if meta.region == "Canada"}
        required = {"XFN.TO", "XEG.TO", "XHC.TO", "XUT.TO", "XMA.TO", "XST.TO", "XIT.TO", "XRE.TO", "XCD.TO"}
        self.assertEqual(set(CANADA_SECTOR_ETFS), required)
        self.assertTrue(required.issubset(canadian_tickers))

    def test_canada_tab_is_scoped_to_canadian_warehouse(self):
        from dashboard.services import build_dashboard_context

        with (
            patch("dashboard.services.get_last_ingestion", return_value=pd.DataFrame()),
            patch("dashboard.services.warehouse_is_populated", return_value=False),
        ):
            context = build_dashboard_context(
                _QueryParams({"tab": "canada", "region": ["US"], "regions_present": ["1"]})
            )

        self.assertEqual(context["regions"], ("Canada",))
        self.assertEqual(context["sector_region"], "Canada")
        self.assertEqual(context["page_title"], "Market Overview - Canada")

    def test_sector_signal_view_shows_all_requested_etfs_and_breadth(self):
        from dashboard.services import US_SECTOR_ETFS, _sector_signal_view

        signals = pd.DataFrame(
            [{
                "price_date": pd.Timestamp("2026-09-30"),
                "ema_spread_pct": 0.02,
                "rsi_14": 72.0,
                "rsi_signal": "Overbought",
                "atr_pct": 0.01,
                "volatility_regime": "High Volatility",
                "trend_signal": "Extended Uptrend",
            }],
            index=pd.Index(["XLK"], name="ticker"),
        )
        fund_info = pd.DataFrame(
            {"aum": [100_000_000_000]}, index=pd.Index(["XLK"], name="ticker")
        )
        with patch("dashboard.services.load_signals_multi", return_value=signals):
            chart, rows, summary, signal_date = _sector_signal_view(pd.DataFrame(), ("US",), fund_info, "US")

        self.assertIsNotNone(chart)
        self.assertEqual(set(row["ticker"] for row in rows), set(US_SECTOR_ETFS))
        self.assertEqual(rows[0]["ticker"], "XLK")
        self.assertEqual(rows[0]["rsi_signal"], "Overbought")
        self.assertEqual(rows[0]["aum"], "$100B")
        self.assertEqual(rows[1]["rsi_signal"], "Insufficient History")
        self.assertEqual(summary[0]["value"], "1")
        self.assertEqual(summary[1]["value"], "1")
        self.assertEqual(summary[3]["value"], "1")
        self.assertEqual(signal_date, "2026-09-30")
        self.assertEqual(chart.layout.yaxis.tickformat, ".1%")
        trace = chart.data[0]
        self.assertEqual(trace.marker.sizemode, "area")
        self.assertEqual(trace.marker.size[0], 100)

    def test_canada_sector_signal_view_reads_canadian_signals(self):
        from dashboard.services import CANADA_SECTOR_ETFS, _sector_signal_view

        signals = pd.DataFrame(
            [{
                "price_date": pd.Timestamp("2026-09-30"),
                "ema_spread_pct": 0.015,
                "rsi_14": 58.0,
                "rsi_signal": "Neutral",
                "atr_pct": 0.012,
                "volatility_regime": "Medium Volatility",
                "trend_signal": "Uptrend",
            }],
            index=pd.Index(["XFN.TO"], name="ticker"),
        )
        fund_info = pd.DataFrame(
            {"aum": [5_000_000_000]}, index=pd.Index(["XFN.TO"], name="ticker")
        )
        with patch("dashboard.services.load_signals_multi", return_value=signals) as load_signals:
            chart, rows, _summary, signal_date = _sector_signal_view(
                pd.DataFrame(), ("Canada",), fund_info, "Canada"
            )

        self.assertIsNotNone(chart)
        self.assertEqual(len(rows), len(CANADA_SECTOR_ETFS))
        self.assertEqual(rows[0]["ticker"], "XFN.TO")
        self.assertEqual(rows[0]["sector"], "Financials")
        self.assertEqual(rows[0]["date"], "09/30/26")
        self.assertEqual(rows[0]["date_full"], "2026-09-30")
        self.assertEqual(rows[0]["aum"], "$5B")
        self.assertEqual(signal_date, "2026-09-30")
        load_signals.assert_called_once_with(["Canada"])


class _QueryParams(dict):
    def getlist(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]