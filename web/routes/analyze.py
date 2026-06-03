"""
Analysis routes — core stock analysis endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from web.models import AnalyzeRequest
from web.api.analysis import analyze_ticker
from web.api.realtime import get_market_status, get_intraday_data, compute_intraday_momentum

router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post("/analyze", summary="Full technical analysis for a ticker")
async def analyze(req: AnalyzeRequest):
    try:
        return analyze_ticker(req.ticker, req.period_years)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.get("/market-status", summary="Current market session status for a ticker")
async def market_status(ticker: str = Query(default="AAPL", description="Ticker to check market for")):
    return get_market_status(ticker.upper())


@router.get("/intraday", summary="Intraday OHLCV data with VWAP")
async def intraday(
    ticker: str = Query(..., description="Stock ticker"),
    interval: str = Query(default="15m", description="Candle interval: 5m, 15m, 30m, 1h"),
):
    data = get_intraday_data(ticker.upper(), interval)
    momentum = compute_intraday_momentum(data)
    return {"intraday": data, "momentum": momentum}
