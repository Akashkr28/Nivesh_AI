"""
Search routes — ticker/company name autocomplete.
"""

from fastapi import APIRouter, Query
from web.api.india_stocks import search_indian_stocks
from yahooquery import search as yq_search

router = APIRouter(prefix="/api", tags=["Search"])


@router.get("/search", summary="Search Indian and global stocks by name or symbol")
async def search_ticker(q: str = Query(..., min_length=2, description="Company name or ticker")):
    if not q or len(q.strip()) < 2:
        return {"suggestions": []}

    results = []

    # 1. Indian stocks from NSE database
    try:
        for r in search_indian_stocks(q, max_results=6):
            results.append({
                "symbol": r["symbol"],
                "query": r["name"],
                "exchange": r.get("exchange", "NSE"),
            })
    except Exception:
        pass

    # 2. Global stocks via yahooquery
    if len(results) < 5:
        try:
            for r in yq_search(q).get("quotes", [])[:5]:
                sym = r.get("symbol", "")
                if not sym or any(c in sym for c in ["=", "/", "^F"]):
                    continue
                if not any(x["symbol"] == sym for x in results):
                    results.append({
                        "symbol": sym,
                        "query": r.get("shortname", r.get("longname", sym)),
                        "exchange": r.get("exchange", ""),
                    })
        except Exception:
            pass

    return {"suggestions": results[:8]}


@router.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "message": "Market Analysis API is running"}
