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
            context = build_dashboard_context(_QueryParams({"region": ["Mars"], "regions_present": ["1"]}))

        self.assertEqual(context["regions"], ())
        self.assertEqual(context["active_tab"], "overview")

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


class _QueryParams(dict):
    def getlist(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]