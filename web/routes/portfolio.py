"""
Portfolio routes — per-user holdings stored in SQLite.
All routes require a valid JWT token.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from web.models import HoldingRequest
from web.auth.database import get_db, Holding
from web.auth.security import decode_token
from web.api.realtime import get_live_quote
from web.api.analysis import fetch_stock_data, add_indicators, detect_regime, compute_metrics
from web.api.prediction import compute_momentum_score
from web.api.india_stocks import resolve_indian_ticker, is_indian_ticker, SYMBOL_OVERRIDES

import yfinance as yf
import uuid

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


# ── Auth dependency ─────────────────────────────────────────────────────────────

def get_user_id(authorization: str = Header(None)) -> str:
    """Returns user_id from JWT, or 'guest' for unauthenticated users."""
    if not authorization or not authorization.startswith("Bearer "):
        return "guest"
    token = authorization.split(" ", 1)[1]
    from web.auth.security import decode_token
    payload = decode_token(token)
    return payload["sub"] if payload else "guest"


# ── Routes ──────────────────────────────────────────────────────────────────────

@router.get("", summary="Get portfolio with live P&L, momentum and regime per holding")
async def get_portfolio(user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    if not holdings:
        return {"holdings": [], "summary": None}

    enriched = [_enrich(h) for h in holdings]

    total_invested = sum(h.get("invested_value", 0) for h in enriched)
    total_current  = sum(h.get("current_value", 0) for h in enriched)
    total_pnl      = total_current - total_invested
    total_pnl_pct  = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    weighted_momentum = 0.0
    if total_current > 0:
        for h in enriched:
            w = h.get("current_value", 0) / total_current
            weighted_momentum += h.get("momentum_score", 50) * w

    risk_flags = []
    for h in enriched:
        if "Bear" in h.get("regime", ""):
            risk_flags.append(f"⚠️ {h['ticker']} is in a {h['regime']} regime")
        if h.get("pnl_pct", 0) < -10:
            risk_flags.append(f"🔴 {h['ticker']} is down {abs(h['pnl_pct']):.1f}% from your buy price")
        if h.get("momentum_score", 50) < 30:
            risk_flags.append(f"📉 {h['ticker']} momentum score is very low ({h.get('momentum_score',0):.0f}/100)")

    summary = {
        "total_invested":    round(total_invested, 2),
        "total_current":     round(total_current, 2),
        "total_pnl":         round(total_pnl, 2),
        "total_pnl_pct":     round(total_pnl_pct, 2),
        "portfolio_momentum": round(weighted_momentum, 1),
        "stock_count":       len(enriched),
        "risk_flags":        risk_flags,
        "as_of":             datetime.now().strftime("%d %b %Y, %H:%M"),
    }
    return {"holdings": enriched, "summary": summary}


@router.post("/add", summary="Add or update a stock holding")
async def add_holding(
    req: HoldingRequest,
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    # Resolve correct symbol
    looks_indian = is_indian_ticker(req.ticker) or req.ticker in SYMBOL_OVERRIDES
    resolved = resolve_indian_ticker(req.ticker) if looks_indian else req.ticker

    # Currency
    currency = "INR" if resolved.endswith(".NS") or resolved.endswith(".BO") else "USD"

    # Company name
    company_name = req.ticker
    try:
        info = yf.Ticker(resolved).fast_info
        company_name = getattr(info, "long_name", None) or req.ticker
    except Exception:
        pass

    # Upsert — update if ticker already exists for this user
    existing = db.query(Holding).filter(
        Holding.user_id == user_id,
        Holding.ticker == req.ticker
    ).first()

    if existing:
        existing.quantity    = req.quantity
        existing.buy_price   = req.buy_price
        existing.buy_date    = req.buy_date or existing.buy_date
        existing.notes       = req.notes or ""
        db.commit()
        return {"status": "updated", "holding": _holding_to_dict(existing)}

    holding = Holding(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=req.ticker,
        resolved_ticker=resolved,
        company_name=company_name,
        quantity=req.quantity,
        buy_price=req.buy_price,
        buy_date=req.buy_date or str(datetime.today().date()),
        notes=req.notes or "",
        currency=currency,
    )
    db.add(holding)
    db.commit()
    return {"status": "added", "holding": _holding_to_dict(holding)}


@router.delete("/{ticker}", summary="Remove a holding")
async def remove_holding(
    ticker: str,
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    holding = db.query(Holding).filter(
        Holding.user_id == user_id,
        Holding.ticker == ticker.upper()
    ).first()
    if not holding:
        raise HTTPException(status_code=404, detail=f"{ticker} not found in your portfolio")
    db.delete(holding)
    db.commit()
    return {"status": "removed", "ticker": ticker.upper()}


@router.delete("", summary="Reset entire portfolio")
async def reset_portfolio(
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    count = db.query(Holding).filter(Holding.user_id == user_id).count()
    db.query(Holding).filter(Holding.user_id == user_id).delete()
    db.commit()
    return {"status": "reset", "removed_count": count}


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _enrich(holding: Holding) -> dict:
    result = _holding_to_dict(holding)
    try:
        quote = get_live_quote(holding.resolved_ticker)
        price = quote.get("price") or 0
        if price > 0:
            invest  = holding.quantity * holding.buy_price
            current = holding.quantity * price
            pnl     = current - invest
            result.update({
                "current_price":  round(price, 2),
                "current_value":  round(current, 2),
                "invested_value": round(invest, 2),
                "pnl":            round(pnl, 2),
                "pnl_pct":        round(pnl / invest * 100, 2) if invest else 0,
                "day_change_pct": quote.get("change_pct", 0),
            })

        df_full, _ = fetch_stock_data(holding.resolved_ticker, period_years=1)
        df_full = add_indicators(df_full)
        regime   = detect_regime(df_full)
        momentum = compute_momentum_score(df_full)
        result["regime"]          = regime["regime"]
        result["regime_color"]    = regime["color"]
        result["momentum_score"]  = momentum["score"]
        result["momentum_label"]  = momentum["label"]
        result["momentum_color"]  = momentum["color"]
    except Exception as e:
        result.setdefault("pnl", 0)
        result.setdefault("pnl_pct", 0)
        result.setdefault("current_price", holding.buy_price)
        result.setdefault("current_value", holding.quantity * holding.buy_price)
        result.setdefault("invested_value", holding.quantity * holding.buy_price)
    return result


def _holding_to_dict(h: Holding) -> dict:
    return {
        "id": h.id, "ticker": h.ticker, "resolved_ticker": h.resolved_ticker,
        "company_name": h.company_name, "quantity": h.quantity,
        "buy_price": h.buy_price, "buy_date": h.buy_date,
        "notes": h.notes, "currency": h.currency,
        "added_at": str(h.added_at),
    }
