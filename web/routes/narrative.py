"""
Narrative routes — plain-English market summaries.
"""

from fastapi import APIRouter, HTTPException
from web.models import AnalyzeRequest
from web.api.analysis import analyze_ticker
from web.api.narrative import build_ai_narrative, build_market_summary

router = APIRouter(prefix="/api", tags=["Narrative"])


@router.post("/narrative", summary="Generate plain-English 'what happened today' for a stock")
async def get_narrative(req: AnalyzeRequest):
    try:
        data = analyze_ticker(req.ticker, req.period_years)
        narrative = build_ai_narrative(data)
        return {
            "ticker": req.ticker,
            "narrative": narrative,
            "as_of": data.get("as_of"),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-summary", summary="Daily overview of Nifty, Sensex and S&P 500")
async def market_summary():
    try:
        return build_market_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
