"""
Indian Stock Market Data Module
================================
Provides full NSE/BSE stock coverage by combining:
1. yahooquery search  — find correct ticker symbols by company name
2. yfinance download  — OHLCV historical data
3. NSE CSV symbol list — all 2000+ listed NSE stocks (auto-downloaded)
4. Smart symbol resolver — handles company name → correct ticker mapping

Why not nsetools/nsepy/jugaad-trader:
  - nsetools: broken JSON parsing on newer NSE API (returns empty)
  - nsepy: broken on Python 3.13 (frame locals issue)
  - jugaad-trader: broker-integration library, not data provider
  - NSE direct API: 403 without browser cookie session

This module uses yahooquery for search (more reliable than yfinance search)
and downloads NSE's official CSV of all listed securities for the symbol DB.
"""

import requests
import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from yahooquery import Ticker, search as yq_search

CACHE_DIR = Path(os.path.dirname(__file__)) / ".." / ".." / "data" / "india_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

NSE_SYMBOL_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
BSE_SYMBOL_CSV_URL = "https://www.bseindia.com/corporates/List_Scrips.aspx"  # needs session

# ── NSE Symbol Database ────────────────────────────────────────────────────────

def download_nse_symbol_list() -> pd.DataFrame:
    """
    Download complete NSE equity symbol list.
    NSE publishes a CSV of all listed securities updated daily.
    Cache locally for 24 hours.
    """
    cache_path = CACHE_DIR / "nse_symbols.csv"

    # Use cache if less than 24h old
    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < 86400:  # 24 hours
            try:
                df = pd.read_csv(cache_path)
                return df
            except Exception:
                pass

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        r = requests.get(NSE_SYMBOL_CSV_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            from io import StringIO
            df = pd.read_csv(StringIO(r.text))
            df.to_csv(cache_path, index=False)
            print(f"Downloaded NSE symbol list: {len(df)} stocks")
            return df
    except Exception as e:
        print(f"Could not download NSE list: {e}")

    # Fallback: return built-in list of top NSE stocks
    return pd.DataFrame(_BUILTIN_NSE_STOCKS, columns=["SYMBOL", "NAME OF COMPANY", "SERIES"])


def get_nse_symbol_db() -> dict:
    """
    Returns dict: company_name_lower → NSE symbol (with .NS suffix).
    Also includes SYMBOL → ticker mapping.
    """
    cache_path = CACHE_DIR / "symbol_db.json"

    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < 86400:
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except Exception:
                pass

    df = download_nse_symbol_list()
    db = {}

    sym_col = next((c for c in df.columns if "SYMBOL" in c.upper()), None)
    name_col = next((c for c in df.columns if "NAME" in c.upper() or "COMPANY" in c.upper()), None)

    if sym_col and name_col:
        for _, row in df.iterrows():
            sym = str(row[sym_col]).strip().upper()
            name = str(row[name_col]).strip()
            if sym and name and sym != "nan":
                # Symbol → ticker
                db[sym] = sym + ".NS"
                # Company name words → symbol
                name_lower = name.lower()
                db[name_lower] = sym + ".NS"
                # First word of company name
                first_word = name_lower.split()[0] if name_lower.split() else ""
                if len(first_word) > 3:
                    db[first_word] = sym + ".NS"

    try:
        with open(cache_path, "w") as f:
            json.dump(db, f)
    except Exception:
        pass

    return db


# ── Smart Symbol Resolution ────────────────────────────────────────────────────

# Manual overrides for commonly searched stocks where yfinance symbol differs
SYMBOL_OVERRIDES = {
    # Tata group restructuring
    "TATAMOTORS":     "TMCV.NS",
    "TATAMOTORS.NS":  "TMCV.NS",
    "TATA MOTORS":    "TMCV.NS",
    "TATAMOTORS-DVR": "TATAMTRDVR.NS",
    # Others with known alternate symbols
    "BAJAJ-AUTO":     "BAJAJ-AUTO.NS",
    "BAJAJ AUTO":     "BAJAJ-AUTO.NS",
    "M&M":            "M&M.NS",
    "MAHINDRA":       "M&M.NS",
    "HERO MOTOCORP":  "HEROMOTOCO.NS",
    "HEROMOTOCORP":   "HEROMOTOCO.NS",
    "DR REDDY":       "DRREDDY.NS",
    "DRREDDY":        "DRREDDY.NS",
    "SHREE CEMENT":   "SHREECEM.NS",
    "SHREECEMENT":    "SHREECEM.NS",
    "DMART":          "DMART.NS",
    "AVENUE SUPERMART": "DMART.NS",
    "ZOMATO":         "ETERNAL.NS",   # Zomato rebranded to Eternal Ltd in 2025
    "ZOMATO.NS":      "ETERNAL.NS",  # redirect old symbol to new one
    "PAYTM":          "PAYTM.NS",
    "NYKAA":          "NYKAA.NS",
    "POLICYBAZAAR":   "POLICYBZR.NS",
    "LIC":            "LICI.NS",
    "SBIN":           "SBIN.NS",
    "SBI":            "SBIN.NS",
    "ONGC":           "ONGC.NS",
    "IOC":            "IOC.NS",
    "BPCL":           "BPCL.NS",
    "NTPC":           "NTPC.NS",
    "COALINDIA":      "COALINDIA.NS",
    "COAL INDIA":     "COALINDIA.NS",
    "JSWSTEEL":       "JSWSTEEL.NS",
    "JSW STEEL":      "JSWSTEEL.NS",
    "HINDALCO":       "HINDALCO.NS",
    "VEDANTA":        "VEDL.NS",
    "GRASIM":         "GRASIM.NS",
    "ULTRACEMCO":     "ULTRACEMCO.NS",
    "ULTRATECH":      "ULTRACEMCO.NS",
    "DIVISLAB":       "DIVISLAB.NS",
    "DIVIS LAB":      "DIVISLAB.NS",
    "CIPLA":          "CIPLA.NS",
    "SUNPHARMA":      "SUNPHARMA.NS",
    "SUN PHARMA":     "SUNPHARMA.NS",
    "TECHM":          "TECHM.NS",
    "TECH MAHINDRA":  "TECHM.NS",
    "HCLTECH":        "HCLTECH.NS",
    "HCL TECH":       "HCLTECH.NS",
    "WIPRO":          "WIPRO.NS",
    "INFOSYS":        "INFY.NS",
    "INFY":           "INFY.NS",
    "TCS":            "TCS.NS",
    "RELIANCE":       "RELIANCE.NS",
    "HDFC BANK":      "HDFCBANK.NS",
    "HDFCBANK":       "HDFCBANK.NS",
    "ICICI BANK":     "ICICIBANK.NS",
    "ICICIBANK":      "ICICIBANK.NS",
    "KOTAK":          "KOTAKBANK.NS",
    "KOTAKBANK":      "KOTAKBANK.NS",
    "AXIS BANK":      "AXISBANK.NS",
    "AXISBANK":       "AXISBANK.NS",
    "BAJFINANCE":     "BAJFINANCE.NS",
    "BAJAJ FINANCE":  "BAJFINANCE.NS",
    "ASIANPAINT":     "ASIANPAINT.NS",
    "ASIAN PAINTS":   "ASIANPAINT.NS",
    "TITAN":          "TITAN.NS",
    "MARUTI":         "MARUTI.NS",
    "ADANIENT":       "ADANIENT.NS",
    "ADANI ENT":      "ADANIENT.NS",
    "ADANIPORTS":     "ADANIPORTS.NS",
    "ADANI PORTS":    "ADANIPORTS.NS",
    "POWERGRID":      "POWERGRID.NS",
    "POWER GRID":     "POWERGRID.NS",
    # Indices
    "NIFTY":          "^NSEI",
    "NIFTY50":        "^NSEI",
    "NIFTY 50":       "^NSEI",
    "SENSEX":         "^BSESN",
    "BANKNIFTY":      "^NSEBANK",
    "BANK NIFTY":     "^NSEBANK",
    "NIFTYIT":        "^CNXIT",
    "NIFTY IT":       "^CNXIT",
}


def resolve_indian_ticker(query: str) -> str:
    """
    Resolve any Indian stock name/symbol to the correct Yahoo Finance ticker.

    Priority:
    1. Manual override table (handles restructured/renamed companies)
    2. NSE symbol database (auto-downloaded list)
    3. yahooquery search (live search by company name)
    4. Direct append of .NS (fallback)
    """
    q = query.strip().upper()
    q_lower = query.strip().lower()

    # 1. Check manual overrides
    if q in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[q]
    if q_lower in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[q_lower]

    # Already has exchange suffix — return as-is
    if q.endswith(".NS") or q.endswith(".BO") or q.startswith("^"):
        return query.upper()

    # 2. Check NSE symbol DB
    try:
        db = get_nse_symbol_db()
        if q in db:
            return db[q]
        if q_lower in db:
            return db[q_lower]
    except Exception:
        pass

    # 3. Live search via yahooquery
    try:
        results = yq_search(query)
        quotes = results.get("quotes", [])
        # Prefer NSE (.NS) results
        for r in quotes:
            sym = r.get("symbol", "")
            if sym.endswith(".NS"):
                return sym
        # Then BSE (.BO)
        for r in quotes:
            sym = r.get("symbol", "")
            if sym.endswith(".BO"):
                return sym
    except Exception:
        pass

    # 4. Fallback: append .NS
    return q + ".NS"


def is_indian_ticker(ticker: str) -> bool:
    t = ticker.upper()
    return (t.endswith(".NS") or t.endswith(".BO") or
            t in {"^NSEI", "^BSESN", "^NSEBANK", "^CNXIT"})


# ── Full NSE Stock Search ──────────────────────────────────────────────────────

def search_indian_stocks(query: str, max_results: int = 10) -> list:
    """
    Search Indian stocks by symbol or company name.
    Returns list of {symbol, name, exchange} dicts.
    """
    results = []
    q_upper = query.strip().upper()
    q_lower = query.strip().lower()

    # 1. Search NSE symbol database
    try:
        df = download_nse_symbol_list()
        sym_col = next((c for c in df.columns if "SYMBOL" in c.upper()), None)
        name_col = next((c for c in df.columns if "NAME" in c.upper() or "COMPANY" in c.upper()), None)

        if sym_col and name_col:
            for _, row in df.iterrows():
                sym = str(row[sym_col]).strip().upper()
                name = str(row[name_col]).strip()
                if (q_upper in sym or q_lower in name.lower()):
                    results.append({
                        "symbol": sym + ".NS",
                        "name": name,
                        "exchange": "NSE",
                    })
                    if len(results) >= max_results:
                        break
    except Exception:
        pass

    # 2. Add overrides that match
    for key, sym in SYMBOL_OVERRIDES.items():
        if q_upper in key.upper() or q_lower in key.lower():
            if not any(r["symbol"] == sym for r in results):
                results.append({
                    "symbol": sym,
                    "name": key.title(),
                    "exchange": "NSE" if sym.endswith(".NS") else "INDEX",
                })

    # 3. yahooquery live search for anything not found locally
    if len(results) < 3:
        try:
            live = yq_search(query)
            for r in live.get("quotes", [])[:5]:
                sym = r.get("symbol", "")
                name = r.get("shortname", r.get("longname", sym))
                exch = r.get("exchange", "")
                if sym.endswith(".NS") or sym.endswith(".BO"):
                    if not any(x["symbol"] == sym for x in results):
                        results.append({"symbol": sym, "name": name, "exchange": exch})
        except Exception:
            pass

    return results[:max_results]


# ── Fetch Data with Indian Fallback ───────────────────────────────────────────

def fetch_with_fallback(ticker: str, period_years: int = 2) -> pd.DataFrame:
    """
    Download OHLCV data trying multiple symbol variants.
    If primary ticker fails, tries:
      - .NS ↔ .BO swap
      - yahooquery search to find the real current symbol
    """
    end = datetime.today()
    fetch_years = max(period_years + 1, 2)
    start = (end - timedelta(days=fetch_years * 365)).strftime("%Y-%m-%d")

    def _try(sym):
        df = yf.download(sym, start=start, end=end.strftime("%Y-%m-%d"),
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # Remove 'Price' level name that breaks ta library
        df.columns.names = [None]
        df.dropna(inplace=True)
        return df if len(df) > 30 else None

    # Primary attempt — try up to 5 years for newly listed stocks
    df = _try(ticker)
    if df is None:
        # Try fetching more history for newly listed / restructured stocks
        old_start = start
        start = (end - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        df = _try(ticker)
        start = old_start
    if df is not None:
        return df, ticker

    # Try .BO if .NS failed
    if ticker.endswith(".NS"):
        alt = ticker.replace(".NS", ".BO")
        df = _try(alt)
        if df is not None:
            return df, alt

    # Try .NS if .BO failed
    if ticker.endswith(".BO"):
        alt = ticker.replace(".BO", ".NS")
        df = _try(alt)
        if df is not None:
            return df, alt

    # Try resolving via yahoo search
    try:
        base = ticker.replace(".NS","").replace(".BO","")
        results = yq_search(base)
        for r in results.get("quotes", []):
            sym = r.get("symbol", "")
            if sym and (sym.endswith(".NS") or sym.endswith(".BO")):
                df = _try(sym)
                if df is not None:
                    return df, sym
    except Exception:
        pass

    # All attempts failed
    raise ValueError(
        f"Could not fetch data for '{ticker}'. "
        f"The stock may have been renamed, delisted, or restructured. "
        f"Try searching by company name (e.g. 'Tata Motors') in the search bar."
    )


# ── Built-in fallback symbol list (in case NSE CSV download fails) ────────────

_BUILTIN_NSE_STOCKS = [
    ("RELIANCE", "Reliance Industries Limited", "EQ"),
    ("TCS", "Tata Consultancy Services Limited", "EQ"),
    ("HDFCBANK", "HDFC Bank Limited", "EQ"),
    ("INFY", "Infosys Limited", "EQ"),
    ("ICICIBANK", "ICICI Bank Limited", "EQ"),
    ("HINDUNILVR", "Hindustan Unilever Limited", "EQ"),
    ("SBIN", "State Bank of India", "EQ"),
    ("BAJFINANCE", "Bajaj Finance Limited", "EQ"),
    ("BHARTIARTL", "Bharti Airtel Limited", "EQ"),
    ("KOTAKBANK", "Kotak Mahindra Bank Limited", "EQ"),
    ("WIPRO", "Wipro Limited", "EQ"),
    ("ASIANPAINT", "Asian Paints Limited", "EQ"),
    ("AXISBANK", "Axis Bank Limited", "EQ"),
    ("MARUTI", "Maruti Suzuki India Limited", "EQ"),
    ("LT", "Larsen and Toubro Limited", "EQ"),
    ("TITAN", "Titan Company Limited", "EQ"),
    ("SUNPHARMA", "Sun Pharmaceutical Industries Limited", "EQ"),
    ("ULTRACEMCO", "UltraTech Cement Limited", "EQ"),
    ("HCLTECH", "HCL Technologies Limited", "EQ"),
    ("ADANIENT", "Adani Enterprises Limited", "EQ"),
    ("ADANIPORTS", "Adani Ports and Special Economic Zone Limited", "EQ"),
    ("ONGC", "Oil and Natural Gas Corporation Limited", "EQ"),
    ("NTPC", "NTPC Limited", "EQ"),
    ("POWERGRID", "Power Grid Corporation of India Limited", "EQ"),
    ("COALINDIA", "Coal India Limited", "EQ"),
    ("TATASTEEL", "Tata Steel Limited", "EQ"),
    ("JSWSTEEL", "JSW Steel Limited", "EQ"),
    ("HINDALCO", "Hindalco Industries Limited", "EQ"),
    ("GRASIM", "Grasim Industries Limited", "EQ"),
    ("TECHM", "Tech Mahindra Limited", "EQ"),
    ("TMCV", "Tata Motors Limited (Commercial Vehicles)", "EQ"),
    ("TMPV", "Tata Motors Passenger Vehicles Limited", "EQ"),
    ("DMART", "Avenue Supermarts Limited", "EQ"),
    ("ZOMATO", "Zomato Limited", "EQ"),
    ("PAYTM", "One97 Communications Limited", "EQ"),
    ("NYKAA", "FSN E-Commerce Ventures Limited", "EQ"),
    ("POLICYBZR", "PB Fintech Limited", "EQ"),
    ("LICI", "Life Insurance Corporation of India", "EQ"),
    ("CIPLA", "Cipla Limited", "EQ"),
    ("DRREDDY", "Dr. Reddy's Laboratories Limited", "EQ"),
    ("DIVISLAB", "Divi's Laboratories Limited", "EQ"),
    ("HEROMOTOCO", "Hero MotoCorp Limited", "EQ"),
    ("BAJAJ-AUTO", "Bajaj Auto Limited", "EQ"),
    ("EICHERMOT", "Eicher Motors Limited", "EQ"),
    ("M&M", "Mahindra and Mahindra Limited", "EQ"),
    ("IOC", "Indian Oil Corporation Limited", "EQ"),
    ("BPCL", "Bharat Petroleum Corporation Limited", "EQ"),
    ("VEDL", "Vedanta Limited", "EQ"),
    ("SHREECEM", "Shree Cement Limited", "EQ"),
    ("INDUSINDBK", "IndusInd Bank Limited", "EQ"),
    ("SBILIFE", "SBI Life Insurance Company Limited", "EQ"),
    ("HDFCLIFE", "HDFC Life Insurance Company Limited", "EQ"),
    ("ICICIGI", "ICICI Lombard General Insurance Company Limited", "EQ"),
    ("PIDILITIND", "Pidilite Industries Limited", "EQ"),
    ("DABUR", "Dabur India Limited", "EQ"),
    ("MARICO", "Marico Limited", "EQ"),
    ("COLPAL", "Colgate-Palmolive (India) Limited", "EQ"),
    ("HAVELLS", "Havells India Limited", "EQ"),
    ("GODREJCP", "Godrej Consumer Products Limited", "EQ"),
    ("BERGEPAINT", "Berger Paints India Limited", "EQ"),
    ("TATACONSUM", "Tata Consumer Products Limited", "EQ"),
    ("ITC", "ITC Limited", "EQ"),
    ("NESTLEIND", "Nestle India Limited", "EQ"),
    ("BRITANNIA", "Britannia Industries Limited", "EQ"),
    ("TATAPOWER", "Tata Power Company Limited", "EQ"),
    ("ADANIGREEN", "Adani Green Energy Limited", "EQ"),
    ("ADANITRANS", "Adani Transmission Limited", "EQ"),
    ("IRCTC", "Indian Railway Catering and Tourism Corporation Limited", "EQ"),
    ("HAL", "Hindustan Aeronautics Limited", "EQ"),
    ("BEL", "Bharat Electronics Limited", "EQ"),
    ("SAIL", "Steel Authority of India Limited", "EQ"),
    ("NMDC", "NMDC Limited", "EQ"),
    ("RECLTD", "REC Limited", "EQ"),
    ("PFC", "Power Finance Corporation Limited", "EQ"),
    ("BANKBARODA", "Bank of Baroda", "EQ"),
    ("PNB", "Punjab National Bank", "EQ"),
    ("CANBK", "Canara Bank", "EQ"),
    ("UNIONBANK", "Union Bank of India", "EQ"),
    ("IDFCFIRSTB", "IDFC First Bank Limited", "EQ"),
    ("BANDHANBNK", "Bandhan Bank Limited", "EQ"),
    ("FEDERALBNK", "The Federal Bank Limited", "EQ"),
    ("RBLBANK", "RBL Bank Limited", "EQ"),
    ("MUTHOOTFIN", "Muthoot Finance Limited", "EQ"),
    ("CHOLAFIN", "Cholamandalam Investment and Finance Company Limited", "EQ"),
    ("MANAPPURAM", "Manappuram Finance Limited", "EQ"),
    ("PERSISTENT", "Persistent Systems Limited", "EQ"),
    ("MPHASIS", "Mphasis Limited", "EQ"),
    ("LTIM", "LTIMindtree Limited", "EQ"),
    ("LTTS", "L&T Technology Services Limited", "EQ"),
    ("COFORGE", "Coforge Limited", "EQ"),
    ("TATAELXSI", "Tata Elxsi Limited", "EQ"),
    ("APOLLOHOSP", "Apollo Hospitals Enterprise Limited", "EQ"),
    ("FORTIS", "Fortis Healthcare Limited", "EQ"),
    ("METROPOLIS", "Metropolis Healthcare Limited", "EQ"),
    ("LALPATHLAB", "Dr. Lal PathLabs Limited", "EQ"),
    ("STAR", "Star Health and Allied Insurance Company Limited", "EQ"),
]
