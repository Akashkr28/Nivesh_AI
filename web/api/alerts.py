"""
Price & Signal Alerts Module
=============================
Users set conditions; the system checks them on demand or on page load.

Alert types:
  - price_above     : notify when price crosses above a level
  - price_below     : notify when price crosses below a level
  - rsi_above       : RSI overbought alert
  - rsi_below       : RSI oversold / buy-dip alert
  - regime_change   : notify when market regime changes
  - momentum_below  : momentum score drops under threshold
  - momentum_above  : momentum score rises above threshold

Storage: JSON file (server-side), simple and portable.
In production this would be a database + email/SMS service.
For now: check on demand and return triggered alerts.
"""

import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.path.dirname(__file__)) / ".." / ".." / "data"
ALERTS_FILE = DATA_DIR / "alerts.json"
ALERT_HISTORY_FILE = DATA_DIR / "alert_history.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ALERT_TYPES = {
    "price_above":    "Price rises above ₹/$ {value}",
    "price_below":    "Price falls below ₹/$ {value}",
    "rsi_above":      "RSI rises above {value} (overbought)",
    "rsi_below":      "RSI falls below {value} (oversold / buy dip)",
    "regime_change":  "Market regime changes",
    "momentum_below": "Momentum score falls below {value}",
    "momentum_above": "Momentum score rises above {value}",
}


# ── Storage ────────────────────────────────────────────────────────────────────

def load_alerts() -> list:
    if not ALERTS_FILE.exists():
        return []
    try:
        with open(ALERTS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_alerts(alerts: list):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2, default=str)


def load_history() -> list:
    if not ALERT_HISTORY_FILE.exists():
        return []
    try:
        with open(ALERT_HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history: list):
    with open(ALERT_HISTORY_FILE, "w") as f:
        json.dump(history[-100:], f, indent=2, default=str)  # keep last 100


# ── CRUD ───────────────────────────────────────────────────────────────────────

def add_alert(ticker: str, alert_type: str, value: float = None, notes: str = "") -> dict:
    """Create a new alert."""
    from web.api.india_stocks import resolve_indian_ticker, is_indian_ticker, SYMBOL_OVERRIDES

    ticker = ticker.upper().strip()
    looks_indian = is_indian_ticker(ticker) or ticker in SYMBOL_OVERRIDES
    resolved = resolve_indian_ticker(ticker) if looks_indian else ticker

    if alert_type not in ALERT_TYPES:
        raise ValueError(f"Unknown alert type: {alert_type}. Valid: {list(ALERT_TYPES.keys())}")

    alert = {
        "id": f"{ticker}_{alert_type}_{int(datetime.now().timestamp())}",
        "ticker": ticker,
        "resolved_ticker": resolved,
        "type": alert_type,
        "value": value,
        "notes": notes,
        "active": True,
        "triggered": False,
        "last_regime": None,   # for regime_change alerts
        "created_at": str(datetime.now()),
        "triggered_at": None,
    }

    alerts = load_alerts()
    alerts.append(alert)
    save_alerts(alerts)
    return alert


def remove_alert(alert_id: str) -> bool:
    alerts = load_alerts()
    new = [a for a in alerts if a["id"] != alert_id]
    if len(new) == len(alerts):
        return False
    save_alerts(new)
    return True


def toggle_alert(alert_id: str) -> dict:
    alerts = load_alerts()
    for a in alerts:
        if a["id"] == alert_id:
            a["active"] = not a["active"]
            save_alerts(alerts)
            return a
    return {}


# ── Alert Checking Engine ──────────────────────────────────────────────────────

def check_all_alerts() -> dict:
    """
    Check every active alert against current market data.
    Returns triggered alerts + status of all alerts.
    """
    import sys
    sys.path.insert(0, str(Path(os.path.dirname(__file__)).parent.parent))
    from web.api.realtime import get_live_quote
    from web.api.analysis import fetch_stock_data, add_indicators, detect_regime, compute_metrics
    from web.api.prediction import compute_momentum_score

    alerts = load_alerts()
    triggered = []
    checked = []

    # Group by ticker to avoid fetching same stock multiple times
    tickers = list(set(a["resolved_ticker"] for a in alerts if a["active"]))
    stock_data = {}

    for ticker in tickers:
        try:
            quote = get_live_quote(ticker)
            df_full, _ = fetch_stock_data(ticker, period_years=1)
            df_full = add_indicators(df_full)
            regime = detect_regime(df_full)
            metrics = compute_metrics(df_full)
            momentum = compute_momentum_score(df_full)

            stock_data[ticker] = {
                "price": quote.get("price", 0),
                "rsi": metrics.get("rsi", 50),
                "regime": regime.get("regime", ""),
                "regime_color": regime.get("color", "gray"),
                "momentum_score": momentum.get("score", 50),
            }
        except Exception as e:
            stock_data[ticker] = {"error": str(e)}

    # Check each alert
    for alert in alerts:
        if not alert.get("active", True):
            checked.append({**alert, "status": "paused"})
            continue

        ticker = alert["resolved_ticker"]
        data = stock_data.get(ticker, {})

        if "error" in data:
            checked.append({**alert, "status": "error", "error": data["error"]})
            continue

        price = data.get("price", 0)
        rsi = data.get("rsi", 50)
        regime = data.get("regime", "")
        momentum = data.get("momentum_score", 50)
        alert_type = alert["type"]
        threshold = alert.get("value")

        is_triggered = False
        trigger_message = ""

        if alert_type == "price_above" and threshold and price >= threshold:
            is_triggered = True
            trigger_message = f"{alert['ticker']} price ₹{price:,.2f} crossed above your alert of ₹{threshold:,.2f}"

        elif alert_type == "price_below" and threshold and price <= threshold:
            is_triggered = True
            trigger_message = f"{alert['ticker']} price ₹{price:,.2f} fell below your alert of ₹{threshold:,.2f}"

        elif alert_type == "rsi_above" and threshold and rsi >= threshold:
            is_triggered = True
            trigger_message = f"{alert['ticker']} RSI is {rsi:.1f} — above your overbought alert of {threshold}"

        elif alert_type == "rsi_below" and threshold and rsi <= threshold:
            is_triggered = True
            trigger_message = f"{alert['ticker']} RSI is {rsi:.1f} — below your oversold alert of {threshold}. Potential buy opportunity."

        elif alert_type == "regime_change":
            last = alert.get("last_regime")
            if last and last != regime:
                is_triggered = True
                trigger_message = f"{alert['ticker']} regime changed: {last} → {regime}"
            # Update stored regime
            alert["last_regime"] = regime

        elif alert_type == "momentum_below" and threshold and momentum <= threshold:
            is_triggered = True
            trigger_message = f"{alert['ticker']} momentum score {momentum:.0f} fell below your alert of {threshold}"

        elif alert_type == "momentum_above" and threshold and momentum >= threshold:
            is_triggered = True
            trigger_message = f"{alert['ticker']} momentum score {momentum:.0f} rose above your alert of {threshold}"

        if is_triggered:
            alert["triggered"] = True
            alert["triggered_at"] = str(datetime.now())
            triggered.append({
                **alert,
                "trigger_message": trigger_message,
                "current_price": price,
                "current_rsi": rsi,
                "current_regime": regime,
                "current_momentum": momentum,
                "status": "triggered",
            })

            # Log to history
            history = load_history()
            history.append({
                "alert_id": alert["id"],
                "ticker": alert["ticker"],
                "message": trigger_message,
                "triggered_at": str(datetime.now()),
            })
            save_history(history)
        else:
            checked.append({
                **alert,
                "current_price": price,
                "current_rsi": rsi,
                "current_regime": regime,
                "current_momentum": momentum,
                "status": "watching",
            })

    save_alerts(alerts)  # save updated last_regime values

    return {
        "triggered": triggered,
        "watching": [a for a in checked if a.get("status") == "watching"],
        "paused": [a for a in checked if a.get("status") == "paused"],
        "errors": [a for a in checked if a.get("status") == "error"],
        "total": len(alerts),
        "triggered_count": len(triggered),
        "checked_at": str(datetime.now().strftime("%d %b %Y, %H:%M:%S")),
    }
