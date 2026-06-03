"""
Portfolio Tracking Module
=========================
Stores user holdings server-side in a JSON file.
No login required — uses a simple session-based approach.

Each holding:
  { ticker, name, quantity, buy_price, buy_date, notes }

On every portfolio refresh:
  - Fetches live price for each holding
  - Computes P&L (unrealized)
  - Runs momentum score + regime for each stock
  - Returns portfolio-level summary
"""

import json
import os
from datetime import datetime
from pathlib import Path
import yfinance as yf

DATA_DIR = Path(os.path.dirname(__file__)) / ".." / ".." / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Storage ────────────────────────────────────────────────────────────────────

def load_portfolio() -> list:
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_portfolio(holdings: list):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(holdings, f, indent=2, default=str)


def add_holding(ticker: str, quantity: float, buy_price: float,
                buy_date: str = None, notes: str = "") -> dict:
    """Add or update a holding."""
    from web.api.india_stocks import resolve_indian_ticker, is_indian_ticker, SYMBOL_OVERRIDES
    from web.api.realtime import get_live_quote

    ticker = ticker.upper().strip()

    # Resolve correct symbol
    looks_indian = (
        is_indian_ticker(ticker) or
        ticker in SYMBOL_OVERRIDES or
        ticker.upper() in SYMBOL_OVERRIDES
    )
    resolved = resolve_indian_ticker(ticker) if looks_indian else ticker

    # Get company name
    try:
        info = yf.Ticker(resolved).fast_info
        currency = getattr(info, 'currency', 'USD') or 'USD'
    except Exception:
        currency = "INR" if resolved.endswith(".NS") or resolved.endswith(".BO") else "USD"

    holdings = load_portfolio()

    # Check if already exists — update instead of duplicate
    for h in holdings:
        if h["ticker"] == ticker:
            h["quantity"] = quantity
            h["buy_price"] = buy_price
            h["buy_date"] = buy_date or h.get("buy_date", str(datetime.today().date()))
            h["notes"] = notes
            save_portfolio(holdings)
            return h

    holding = {
        "id": f"{ticker}_{int(datetime.now().timestamp())}",
        "ticker": ticker,
        "resolved_ticker": resolved,
        "quantity": quantity,
        "buy_price": buy_price,
        "buy_date": buy_date or str(datetime.today().date()),
        "notes": notes,
        "currency": currency,
        "added_at": str(datetime.now()),
    }
    holdings.append(holding)
    save_portfolio(holdings)
    return holding


def remove_holding(ticker: str) -> bool:
    holdings = load_portfolio()
    new = [h for h in holdings if h["ticker"] != ticker.upper().strip()]
    if len(new) == len(holdings):
        return False
    save_portfolio(new)
    return True


# ── Enrichment ─────────────────────────────────────────────────────────────────

def enrich_holding(holding: dict) -> dict:
    """
    Add live price, P&L, momentum, and regime to a holding.
    Runs full analysis for each stock.
    """
    import sys
    sys.path.insert(0, str(Path(os.path.dirname(__file__)).parent.parent))

    from web.api.realtime import get_live_quote
    from web.api.analysis import fetch_stock_data, add_indicators, detect_regime, compute_metrics
    from web.api.prediction import compute_momentum_score

    ticker = holding.get("resolved_ticker") or holding["ticker"]
    result = {**holding}

    try:
        # Live quote
        quote = get_live_quote(ticker)
        current_price = quote.get("price") or 0

        if current_price > 0:
            invest = holding["quantity"] * holding["buy_price"]
            current_val = holding["quantity"] * current_price
            pnl = current_val - invest
            pnl_pct = (pnl / invest * 100) if invest > 0 else 0

            result["current_price"] = round(current_price, 2)
            result["current_value"] = round(current_val, 2)
            result["invested_value"] = round(invest, 2)
            result["pnl"] = round(pnl, 2)
            result["pnl_pct"] = round(pnl_pct, 2)
            result["day_change_pct"] = quote.get("change_pct", 0)
        else:
            result["current_price"] = holding["buy_price"]
            result["pnl"] = 0
            result["pnl_pct"] = 0

        # Quick regime + momentum (use 1Y data)
        df_full, _ = fetch_stock_data(ticker, period_years=1)
        df_full = add_indicators(df_full)

        regime = detect_regime(df_full)
        momentum = compute_momentum_score(df_full)

        result["regime"] = regime["regime"]
        result["regime_color"] = regime["color"]
        result["momentum_score"] = momentum["score"]
        result["momentum_label"] = momentum["label"]
        result["momentum_color"] = momentum["color"]

        # Company name
        try:
            info = yf.Ticker(ticker).fast_info
            result["company_name"] = getattr(info, 'long_name', None) or ticker
        except Exception:
            result["company_name"] = ticker

    except Exception as e:
        result["error"] = str(e)
        result["current_price"] = holding.get("buy_price", 0)
        result["pnl"] = 0
        result["pnl_pct"] = 0

    return result


def get_portfolio_summary() -> dict:
    """
    Full portfolio snapshot:
    - Each holding with live P&L, momentum, regime
    - Portfolio-level totals and allocation breakdown
    """
    holdings = load_portfolio()
    if not holdings:
        return {"holdings": [], "summary": None}

    enriched = []
    for h in holdings:
        enriched.append(enrich_holding(h))

    # Portfolio totals
    total_invested = sum(h.get("invested_value", 0) for h in enriched)
    total_current = sum(h.get("current_value", 0) for h in enriched)
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    # Count regimes
    regime_counts = {}
    for h in enriched:
        r = h.get("regime", "Unknown")
        regime_counts[r] = regime_counts.get(r, 0) + 1

    # Portfolio momentum (weighted by value)
    weighted_momentum = 0
    if total_current > 0:
        for h in enriched:
            weight = h.get("current_value", 0) / total_current
            weighted_momentum += h.get("momentum_score", 50) * weight

    # Risk flags
    alerts = []
    for h in enriched:
        if "Bear" in h.get("regime", ""):
            alerts.append(f"⚠️ {h['ticker']} is in a {h['regime']} regime")
        if h.get("pnl_pct", 0) < -10:
            alerts.append(f"🔴 {h['ticker']} is down {abs(h['pnl_pct']):.1f}% from your buy price")
        if h.get("momentum_score", 50) < 30:
            alerts.append(f"📉 {h['ticker']} has strong bearish momentum ({h.get('momentum_score',0):.0f}/100)")

    summary = {
        "total_invested": round(total_invested, 2),
        "total_current": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "portfolio_momentum": round(weighted_momentum, 1),
        "regime_breakdown": regime_counts,
        "stock_count": len(enriched),
        "risk_flags": alerts,
        "as_of": str(datetime.now().strftime("%d %b %Y, %H:%M")),
    }

    return {"holdings": enriched, "summary": summary}
