import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import duckdb
import numpy as np
import pandas as pd

from data_engine import compute_technical_indicators, compute_technical_signals, fetch_price_history, fetch_price_ohlc
from warehouse.ingest import run_ingestion


class TechnicalIndicatorTests(unittest.TestCase):
    def test_flat_prices_have_neutral_rsi_and_zero_spread(self):
        dates = pd.bdate_range("2025-01-01", periods=220)
        prices = pd.DataFrame({"high": 101.0, "low": 99.0, "close": 100.0}, index=dates)

        result = compute_technical_indicators(prices)

        self.assertEqual(result.loc[dates[199], "ema_50"], 100.0)
        self.assertEqual(result.loc[dates[199], "ema_200"], 100.0)
        self.assertEqual(result.loc[dates[199], "ema_spread"], 0.0)
        self.assertEqual(result.loc[dates[199], "rsi_14"], 50.0)
        self.assertEqual(result.loc[dates[199], "atr_14"], 2.0)
        self.assertEqual(result.loc[dates[199], "rsi_signal"], "Neutral")
        self.assertEqual(result.loc[dates[199], "volatility_regime"], "Medium Volatility")
        self.assertEqual(result.loc[dates[199], "trend_signal"], "Neutral")

    def test_indicator_warmups_and_directional_values(self):
        dates = pd.bdate_range("2025-01-01", periods=220)
        close = pd.Series(np.arange(100.0, 320.0), index=dates)
        prices = pd.DataFrame({"high": close + 1, "low": close - 1, "close": close})

        result = compute_technical_indicators(prices)

        self.assertEqual(result["ema_50"].first_valid_index(), dates[49])
        self.assertEqual(result["ema_200"].first_valid_index(), dates[199])
        self.assertEqual(result["rsi_14"].iloc[-1], 100.0)
        self.assertAlmostEqual(result["atr_14"].iloc[-1], 2.0)
        self.assertGreater(result["ema_spread"].iloc[-1], 0.0)

    def test_signal_bands_phase_changes_and_warmup(self):
        dates = pd.bdate_range("2025-01-01", periods=300)
        atr_percent = np.tile([0.01, 0.02, 0.03], 100)
        spread_percent = np.zeros(300)
        spread_percent[298] = 0.004
        spread_percent[299] = 0.006
        rsi = np.full(300, 50.0)
        rsi[-3:] = [29.0, 70.0, 71.0]
        indicators = pd.DataFrame(
            {
                "close": 100.0,
                "ema_200": 100.0,
                "ema_spread": spread_percent * 100.0,
                "rsi_14": rsi,
                "atr_14": atr_percent * 100.0,
            },
            index=dates,
        )

        result = compute_technical_signals(indicators)

        self.assertEqual(result["rsi_signal"].iloc[-3:].tolist(), ["Oversold", "Overbought", "Overbought"])
        self.assertEqual(result["volatility_regime"].iloc[0], "Insufficient History")
        self.assertEqual(result["volatility_regime"].iloc[-2], "Medium Volatility")
        self.assertEqual(result["volatility_regime"].iloc[-1], "High Volatility")
        self.assertEqual(result["trend_signal"].iloc[298], "Neutral")
        self.assertEqual(result["trend_signal"].iloc[299], "Entering Uptrend")

        indicators.iloc[-2:, indicators.columns.get_loc("ema_spread")] = 6.0
        extended = compute_technical_signals(indicators)
        self.assertEqual(extended["trend_signal"].iloc[-1], "Extended Uptrend")

        indicators.iloc[-1, indicators.columns.get_loc("atr_14")] = 0.5
        low_volatility = compute_technical_signals(indicators)
        self.assertEqual(low_volatility["volatility_regime"].iloc[-1], "Low Volatility")

    @patch("data_engine.yf.download")
    def test_ohlc_fetcher_handles_single_ticker_shape(self, download):
        dates = pd.date_range("2026-01-01", periods=2)
        download.return_value = pd.DataFrame(
            {"High": [11.0, 12.0], "Low": [9.0, 10.0], "Close": [10.0, 11.0]},
            index=dates,
        )

        result = fetch_price_ohlc(["SPY"])

        self.assertEqual(result.columns.tolist(), ["price_date", "high", "low", "close", "ticker"])
        self.assertEqual(result["ticker"].tolist(), ["SPY", "SPY"])
        self.assertEqual(result["close"].tolist(), [10.0, 11.0])

    @patch("data_engine.yf.download")
    def test_existing_close_history_api_stays_wide(self, download):
        dates = pd.date_range("2026-01-01", periods=2)
        columns = pd.MultiIndex.from_product([["SPY", "VTI"], ["High", "Low", "Close"]])
        download.return_value = pd.DataFrame(
            [[11, 9, 10, 21, 19, 20], [12, 10, 11, 22, 20, 21]],
            columns=columns,
            index=dates,
        )

        result = fetch_price_history(["SPY", "VTI"])

        self.assertEqual(result.columns.tolist(), ["SPY", "VTI"])
        self.assertEqual(result.iloc[-1].to_dict(), {"SPY": 11.0, "VTI": 21.0})


class WarehouseIngestionTests(unittest.TestCase):
    def test_ingestion_maps_ohlc_by_name_for_legacy_price_table(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.duckdb"
            setup = duckdb.connect(str(database_path))
            setup.execute("CREATE SCHEMA us_etf; CREATE SCHEMA ca_etf")
            setup.execute(
                """CREATE TABLE us_etf.funds (
                    ticker VARCHAR, name VARCHAR, category VARCHAR, issuer VARCHAR,
                    region VARCHAR, currency VARCHAR, aum DOUBLE, expense_ratio DOUBLE,
                    dividend_yield DOUBLE, last_updated TIMESTAMP
                )"""
            )
            setup.execute(
                "CREATE TABLE us_etf.prices (ticker VARCHAR, price_date DATE, close DOUBLE, PRIMARY KEY (ticker, price_date))"
            )
            setup.execute(
                """CREATE TABLE main.ingestion_log (
                    run_id VARCHAR PRIMARY KEY, region VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP,
                    tickers_requested INTEGER, tickers_loaded INTEGER, price_rows_upserted INTEGER,
                    status VARCHAR, note VARCHAR
                )"""
            )
            setup.close()

            dates = pd.bdate_range("2025-01-01", periods=205)
            close = np.arange(100.0, 305.0)
            prices = pd.DataFrame(
                {
                    "ticker": "SPY",
                    "price_date": dates,
                    "high": close + 2.0,
                    "low": close - 1.0,
                    "close": close + 0.5,
                }
            )
            funds = pd.DataFrame(
                [{
                    "ticker": "SPY", "name": "SPY", "category": "Equity", "issuer": "Test",
                    "region": "US", "currency": "USD", "aum": 1_000_000_000.0,
                    "expense_ratio": 0.001, "dividend_yield": 0.01,
                }]
            ).set_index("ticker")

            def connect_with_schema(read_only=False):
                connection = duckdb.connect(str(database_path), read_only=read_only)
                if not read_only:
                    connection.execute(Path("warehouse/schema.sql").read_text())
                return connection

            with (
                patch("warehouse.ingest.get_connection", side_effect=connect_with_schema),
                patch("warehouse.ingest.fetch_fund_info", return_value=funds),
                patch("warehouse.ingest.fetch_price_ohlc", return_value=prices),
            ):
                summary = run_ingestion("US", tickers=["SPY"])

            self.assertEqual(summary["status"], "success", summary["note"])
            self.assertEqual(summary["price_rows_upserted"], len(prices))
            verify = duckdb.connect(str(database_path), read_only=True)
            stored = verify.execute(
                "SELECT high, low, close, atr_14, rsi_signal, volatility_regime, trend_signal "
                "FROM us_etf.prices ORDER BY price_date DESC LIMIT 1"
            ).fetchone()
            verify.close()

            self.assertEqual(stored[:3], (306.0, 303.0, 304.5))
            self.assertEqual(stored[3], 3.0)
            self.assertEqual(stored[4], "Overbought")
            self.assertEqual(stored[6], "Extended Uptrend")


if __name__ == "__main__":
    unittest.main()