"""
Alerts routes — CRUD for price/signal alerts and alert checking.
"""

from fastapi import APIRouter, HTTPException
from web.models import AlertRequest
from web.api.alerts import (
    load_alerts,
    load_history,
    add_alert,
    remove_alert,
    check_all_alerts,
)

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", summary="List all alerts and recent trigger history")
async def get_alerts():
    return {
        "alerts": load_alerts(),
        "history": load_history()[-10:],
    }


@router.post("/add", summary="Create a new alert")
async def create_alert(req: AlertRequest):
    try:
        alert = add_alert(
            ticker=req.ticker,
            alert_type=req.alert_type,
            value=req.value,
            notes=req.notes or "",
        )
        return {"status": "created", "alert": alert}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{alert_id}", summary="Delete an alert by ID")
async def delete_alert(alert_id: str):
    removed = remove_alert(alert_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "deleted", "alert_id": alert_id}


@router.get("/check", summary="Check all active alerts against current market data")
async def check_alerts():
    try:
        return check_all_alerts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
