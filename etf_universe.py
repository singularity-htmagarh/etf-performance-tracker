"""
etf_universe.py
----------------
Curated universe of large, liquid US and Canadian-listed ETFs.
 
This is a *candidate* list only. Actual inclusion in the tracker is
decided at runtime by the AUM filter (AUM > $1B) applied in app.py,
using live `totalAssets` pulled from yfinance. Keeping a curated
candidate list (rather than scanning the whole tape) keeps API calls
bounded and avoids pulling in thin/derivative/leveraged products that
happen to have a ticker but no business being called "core liquid
beta" for an institutional tracker.
 
Canadian tickers use the Yahoo Finance ".TO" (Toronto Stock Exchange)
suffix required by yfinance.
"""
 
from __future__ import annotations
from dataclasses import dataclass
 
 
@dataclass(frozen=True)
class ETFMeta:
    ticker: str
    name: str
    region: str        # "US" or "Canada"
    category: str       # asset-class / style bucket
    issuer: str
 
 
UNIVERSE: list[ETFMeta] = [
    # ---------------- US : Broad Equity ----------------
    ETFMeta("SPY", "SPDR S&P 500 ETF Trust", "US", "US Broad Equity", "State Street"),
    ETFMeta("IVV", "iShares Core S&P 500 ETF", "US", "US Broad Equity", "BlackRock"),
    ETFMeta("VOO", "Vanguard S&P 500 ETF", "US", "US Broad Equity", "Vanguard"),
    ETFMeta("VTI", "Vanguard Total Stock Market ETF", "US", "US Broad Equity", "Vanguard"),
    ETFMeta("QQQ", "Invesco QQQ Trust", "US", "US Broad Equity", "Invesco"),
    ETFMeta("QQQM", "Invesco NASDAQ 100 ETF", "US", "US Broad Equity", "Invesco"),
    ETFMeta("DIA", "SPDR Dow Jones Industrial Average ETF", "US", "US Broad Equity", "State Street"),
    ETFMeta("IWM", "iShares Russell 2000 ETF", "US", "US Small Cap", "BlackRock"),
    ETFMeta("IJH", "iShares Core S&P Mid-Cap ETF", "US", "US Mid Cap", "BlackRock"),
    ETFMeta("IJR", "iShares Core S&P Small-Cap ETF", "US", "US Small Cap", "BlackRock"),
    ETFMeta("MDY", "SPDR S&P MidCap 400 ETF Trust", "US", "US Mid Cap", "State Street"),
    ETFMeta("SCHX", "Schwab U.S. Large-Cap ETF", "US", "US Broad Equity", "Schwab"),
    ETFMeta("SCHB", "Schwab U.S. Broad Market ETF", "US", "US Broad Equity", "Schwab"),
    ETFMeta("ITOT", "iShares Core S&P Total U.S. Stock Market ETF", "US", "US Broad Equity", "BlackRock"),
    ETFMeta("RSP", "Invesco S&P 500 Equal Weight ETF", "US", "US Broad Equity", "Invesco"),
 
    # ---------------- US : Style / Factor ----------------
    ETFMeta("VUG", "Vanguard Growth ETF", "US", "US Style", "Vanguard"),
    ETFMeta("VTV", "Vanguard Value ETF", "US", "US Style", "Vanguard"),
    ETFMeta("IWF", "iShares Russell 1000 Growth ETF", "US", "US Style", "BlackRock"),
    ETFMeta("IWD", "iShares Russell 1000 Value ETF", "US", "US Style", "BlackRock"),
    ETFMeta("SPYG", "SPDR Portfolio S&P 500 Growth ETF", "US", "US Style", "State Street"),
    ETFMeta("SPYV", "SPDR Portfolio S&P 500 Value ETF", "US", "US Style", "State Street"),
    ETFMeta("SCHD", "Schwab U.S. Dividend Equity ETF", "US", "US Dividend", "Schwab"),
    ETFMeta("VYM", "Vanguard High Dividend Yield ETF", "US", "US Dividend", "Vanguard"),
    ETFMeta("DVY", "iShares Select Dividend ETF", "US", "US Dividend", "BlackRock"),
    ETFMeta("SDY", "SPDR S&P Dividend ETF", "US", "US Dividend", "State Street"),
    ETFMeta("NOBL", "ProShares S&P 500 Dividend Aristocrats ETF", "US", "US Dividend", "ProShares"),
    ETFMeta("JEPI", "JPMorgan Equity Premium Income ETF", "US", "US Income/Options", "JPMorgan"),
    ETFMeta("JEPQ", "JPMorgan Nasdaq Equity Premium Income ETF", "US", "US Income/Options", "JPMorgan"),
    ETFMeta("ARKK", "ARK Innovation ETF", "US", "US Thematic", "ARK"),
 
    # ---------------- US : Sector (SPDR Select Sector) ----------------
    ETFMeta("XLK", "Technology Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLF", "Financial Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLE", "Energy Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLV", "Health Care Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLY", "Consumer Discretionary Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLP", "Consumer Staples Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLI", "Industrial Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLB", "Materials Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLU", "Utilities Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLRE", "Real Estate Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("XLC", "Communication Services Select Sector SPDR Fund", "US", "US Sector", "State Street"),
    ETFMeta("VNQ", "Vanguard Real Estate ETF", "US", "US Sector", "Vanguard"),
 
    # ---------------- US : International / Global ----------------
    ETFMeta("VEA", "Vanguard FTSE Developed Markets ETF", "US", "International Equity", "Vanguard"),
    ETFMeta("VWO", "Vanguard FTSE Emerging Markets ETF", "US", "Emerging Markets Equity", "Vanguard"),
    ETFMeta("EFA", "iShares MSCI EAFE ETF", "US", "International Equity", "BlackRock"),
    ETFMeta("EEM", "iShares MSCI Emerging Markets ETF", "US", "Emerging Markets Equity", "BlackRock"),
    ETFMeta("IEFA", "iShares Core MSCI EAFE ETF", "US", "International Equity", "BlackRock"),
    ETFMeta("IEMG", "iShares Core MSCI Emerging Markets ETF", "US", "Emerging Markets Equity", "BlackRock"),
    ETFMeta("ACWI", "iShares MSCI ACWI ETF", "US", "Global Equity", "BlackRock"),
    ETFMeta("VT", "Vanguard Total World Stock ETF", "US", "Global Equity", "Vanguard"),
    ETFMeta("VXUS", "Vanguard Total International Stock ETF", "US", "International Equity", "Vanguard"),
 
    # ---------------- US : Fixed Income ----------------
    ETFMeta("AGG", "iShares Core U.S. Aggregate Bond ETF", "US", "US Fixed Income", "BlackRock"),
    ETFMeta("BND", "Vanguard Total Bond Market ETF", "US", "US Fixed Income", "Vanguard"),
    ETFMeta("LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "US", "US Corporate Credit", "BlackRock"),
    ETFMeta("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "US", "US High Yield Credit", "BlackRock"),
    ETFMeta("TLT", "iShares 20+ Year Treasury Bond ETF", "US", "US Treasuries", "BlackRock"),
    ETFMeta("IEF", "iShares 7-10 Year Treasury Bond ETF", "US", "US Treasuries", "BlackRock"),
    ETFMeta("SHY", "iShares 1-3 Year Treasury Bond ETF", "US", "US Treasuries", "BlackRock"),
    ETFMeta("TIP", "iShares TIPS Bond ETF", "US", "US Inflation-Linked", "BlackRock"),
    ETFMeta("MUB", "iShares National Muni Bond ETF", "US", "US Municipal", "BlackRock"),
    ETFMeta("BNDX", "Vanguard Total International Bond ETF", "US", "International Fixed Income", "Vanguard"),
    ETFMeta("EMB", "iShares JP Morgan USD Emerging Markets Bond ETF", "US", "EM Fixed Income", "BlackRock"),
 
    # ---------------- US : Commodities ----------------
    ETFMeta("GLD", "SPDR Gold Shares", "US", "Commodities", "State Street"),
    ETFMeta("SLV", "iShares Silver Trust", "US", "Commodities", "BlackRock"),
    ETFMeta("USO", "United States Oil Fund", "US", "Commodities", "USCF"),
 
    # ---------------- Canada (TSX, .TO) ----------------
    ETFMeta("XIU.TO", "iShares S&P/TSX 60 Index ETF", "Canada", "Canada Broad Equity", "BlackRock"),
    ETFMeta("XIC.TO", "iShares Core S&P/TSX Capped Composite ETF", "Canada", "Canada Broad Equity", "BlackRock"),
    ETFMeta("ZCN.TO", "BMO S&P/TSX Capped Composite Index ETF", "Canada", "Canada Broad Equity", "BMO"),
    ETFMeta("VCN.TO", "Vanguard FTSE Canada All Cap Index ETF", "Canada", "Canada Broad Equity", "Vanguard"),
    ETFMeta("ZSP.TO", "BMO S&P 500 Index ETF", "Canada", "US Equity (CAD)", "BMO"),
    ETFMeta("VFV.TO", "Vanguard S&P 500 Index ETF (CAD-hedged/unhedged)", "Canada", "US Equity (CAD)", "Vanguard"),
    ETFMeta("XSP.TO", "iShares Core S&P 500 Index ETF (CAD-Hedged)", "Canada", "US Equity (CAD)", "BlackRock"),
    ETFMeta("XUU.TO", "iShares Core S&P U.S. Total Market Index ETF", "Canada", "US Equity (CAD)", "BlackRock"),
    ETFMeta("VUN.TO", "Vanguard U.S. Total Market Index ETF", "Canada", "US Equity (CAD)", "Vanguard"),
    ETFMeta("XQQ.TO", "iShares NASDAQ 100 Index ETF (CAD-Hedged)", "Canada", "US Equity (CAD)", "BlackRock"),
    ETFMeta("ZQQ.TO", "BMO NASDAQ 100 Equity Hedged to CAD Index ETF", "Canada", "US Equity (CAD)", "BMO"),
    ETFMeta("XEF.TO", "iShares Core MSCI EAFE IMI Index ETF", "Canada", "International Equity (CAD)", "BlackRock"),
    ETFMeta("XEC.TO", "iShares Core MSCI Emerging Markets IMI Index ETF", "Canada", "Emerging Markets (CAD)", "BlackRock"),
    ETFMeta("ZEB.TO", "BMO Equal Weight Banks Index ETF", "Canada", "Canada Sector", "BMO"),
    ETFMeta("XDV.TO", "iShares Canadian Select Dividend Index ETF", "Canada", "Canada Dividend", "BlackRock"),
    ETFMeta("VDY.TO", "Vanguard FTSE Canadian High Dividend Yield Index ETF", "Canada", "Canada Dividend", "Vanguard"),
    ETFMeta("ZDV.TO", "BMO Canadian Dividend ETF", "Canada", "Canada Dividend", "BMO"),
    ETFMeta("XBB.TO", "iShares Core Canadian Universe Bond Index ETF", "Canada", "Canada Fixed Income", "BlackRock"),
    ETFMeta("ZAG.TO", "BMO Aggregate Bond Index ETF", "Canada", "Canada Fixed Income", "BMO"),
    ETFMeta("VAB.TO", "Vanguard Canadian Aggregate Bond Index ETF", "Canada", "Canada Fixed Income", "Vanguard"),
    ETFMeta("HXT.TO", "Global X S&P/TSX 60 Index Corporate Class ETF", "Canada", "Canada Broad Equity", "Global X"),
]
 
ALL_TICKERS: list[str] = [m.ticker for m in UNIVERSE]
META_BY_TICKER: dict[str, ETFMeta] = {m.ticker: m for m in UNIVERSE}