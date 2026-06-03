"""
Real-time & intraday market data module.

Fetches:
- Today's intraday price movement (5-minute intervals)
- Live quote: current price, bid/ask, volume
- Pre-market / after-market data where available
- Indian market session detection (NSE/BSE)

yfinance supports intraday data:
  interval="1m"  → last 7 days
  interval="5m"  → last 60 days
  interval="15m" → last 60 days
  interval="1h"  → last 730 days
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz


# ── Market Session Detection ──────────────────────────────────────────────────

MARKET_SESSIONS = {
    "US": {
        "tz": "America/New_York",
        "open": (9, 30),
        "close": (16, 0),
        "pre_open": (4, 0),
        "after_close": (20, 0),
        "label": "US Market (NYSE/NASDAQ)",
        "tickers_hint": "AAPL, TSLA, NVDA, SPY, QQQ",
    },
    "IN": {
        "tz": "Asia/Kolkata",
        "open": (9, 15),
        "close": (15, 30),
        "pre_open": (9, 0),
        "after_close": (16, 0),
        "label": "Indian Market (NSE/BSE)",
        "tickers_hint": "RELIANCE.NS, TCS.NS, INFY.NS, ^NSEI, ^BSESN",
    },
}

INDIAN_SUFFIXES = (".NS", ".BO")
INDIAN_INDICES = {"^NSEI", "^BSESN", "^NSEBANK", "NIFTY50.NS"}


def detect_market(ticker: str) -> str:
    t = ticker.upper()
    if any(t.endswith(s) for s in INDIAN_SUFFIXES) or t in INDIAN_INDICES:
        return "IN"
    return "US"


def get_market_status(ticker: str) -> dict:
    market = detect_market(ticker)
    session = MARKET_SESSIONS[market]
    tz = pytz.timezone(session["tz"])
    now = datetime.now(tz)
    weekday = now.weekday()  # 0=Mon, 6=Sun

    open_h, open_m = session["open"]
    close_h, close_m = session["close"]
    pre_h, pre_m = session["pre_open"]

    market_open = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    market_close = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    pre_open = now.replace(hour=pre_h, minute=pre_m, second=0, microsecond=0)

    if weekday >= 5:
        status = "closed"
        status_label = "Weekend — Market Closed"
        status_color = "gray"
    elif now < pre_open:
        status = "pre_market"
        status_label = "Pre-Market"
        status_color = "orange"
    elif pre_open <= now < market_open:
        status = "pre_market"
        status_label = "Pre-Market Session"
        status_color = "orange"
    elif market_open <= now <= market_close:
        status = "open"
        status_label = "🟢 Market Open"
        status_color = "green"
    else:
        status = "after_hours"
        status_label = "After Hours"
        status_color = "orange"

    return {
        "market": market,
        "market_label": session["label"],
        "status": status,
        "status_label": status_label,
        "status_color": status_color,
        "local_time": now.strftime("%H:%M %Z"),
        "local_date": now.strftime("%A, %d %b %Y"),
    }


# ── Live Quote ────────────────────────────────────────────────────────────────

def get_live_quote(ticker: str) -> dict:
    """
    Fetch the most current price data available.
    yfinance returns real-time delayed quotes (15-min delay for free tier).
    """
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info

        price = float(getattr(info, 'last_price', 0) or 0)
        prev_close = float(getattr(info, 'previous_close', 0) or 0)
        day_high = float(getattr(info, 'day_high', 0) or 0)
        day_low = float(getattr(info, 'day_low', 0) or 0)
        volume = int(getattr(info, 'last_volume', 0) or 0)
        market_cap = float(getattr(info, 'market_cap', 0) or 0)

        change = price - prev_close if price and prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        # 52-week range
        week52_high = float(getattr(info, 'fifty_two_week_high', 0) or 0)
        week52_low = float(getattr(info, 'fifty_two_week_low', 0) or 0)

        # Position in 52-week range (0% = at low, 100% = at high)
        range_pct = 0.0
        if week52_high > week52_low:
            range_pct = (price - week52_low) / (week52_high - week52_low) * 100

        return {
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "volume": volume,
            "week52_high": round(week52_high, 2),
            "week52_low": round(week52_low, 2),
            "week52_range_pct": round(range_pct, 1),
            "market_cap": market_cap,
        }
    except Exception as e:
        return {"error": str(e), "price": 0, "change_pct": 0}


# ── Intraday Chart ─────────────────────────────────────────────────────────────

def get_intraday_data(ticker: str, interval: str = "15m") -> dict:
    """
    Fetch intraday price data for today's session.
    Returns OHLCV + VWAP for charting.

    interval options: "5m", "15m", "30m", "1h"
    """
    try:
        # Fetch last 5 days to ensure we get today even on market open
        df = yf.download(
            ticker,
            period="5d",
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            return {"error": "No intraday data available", "candles": []}

        df.dropna(inplace=True)

        # Get today's data only (or last trading day)
        market = detect_market(ticker)
        tz_name = MARKET_SESSIONS[market]["tz"]
        tz = pytz.timezone(tz_name)

        # Convert index to local timezone
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(tz)

        # Get most recent trading day's data
        last_date = df.index[-1].date()
        today_df = df[df.index.date == last_date]

        if today_df.empty:
            today_df = df.tail(40)  # fallback: last 40 candles

        # VWAP = (cumulative price*volume) / cumulative volume
        typical_price = (today_df["High"] + today_df["Low"] + today_df["Close"]) / 3
        vwap = (typical_price * today_df["Volume"]).cumsum() / today_df["Volume"].cumsum()

        candles = []
        for ts, row in today_df.iterrows():
            candles.append({
                "time": ts.strftime("%H:%M"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        vwap_list = [round(float(v), 2) if not pd.isna(v) else None for v in vwap]
        times = [ts.strftime("%H:%M") for ts in today_df.index]

        # Intraday stats
        if len(today_df) > 0:
            open_price = float(today_df.iloc[0]["Open"])
            current = float(today_df.iloc[-1]["Close"])
            intraday_change = (current - open_price) / open_price * 100
            intraday_high = float(today_df["High"].max())
            intraday_low = float(today_df["Low"].min())
            avg_volume = float(today_df["Volume"].mean())
            total_volume = int(today_df["Volume"].sum())
        else:
            open_price = current = intraday_change = intraday_high = intraday_low = 0
            avg_volume = total_volume = 0

        return {
            "date": str(last_date),
            "interval": interval,
            "candles": candles,
            "times": times,
            "vwap": vwap_list,
            "open_price": round(open_price, 2),
            "current_price": round(current, 2),
            "intraday_change_pct": round(intraday_change, 2),
            "intraday_high": round(intraday_high, 2),
            "intraday_low": round(intraday_low, 2),
            "total_volume": total_volume,
            "candle_count": len(candles),
        }

    except Exception as e:
        return {"error": str(e), "candles": []}


# ── Intraday Momentum ──────────────────────────────────────────────────────────

def compute_intraday_momentum(intraday: dict) -> dict:
    """
    Analyze the intraday session for momentum patterns:
    - Opening gap (vs previous close)
    - Trend direction within session
    - Volume pattern (climactic vs drying up)
    - Breakout or range-bound behavior
    """
    candles = intraday.get("candles", [])
    if len(candles) < 4:
        return {"label": "Insufficient intraday data", "score": 0}

    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    # Trend: linear regression slope of closes
    x = np.arange(len(closes))
    slope = np.polyfit(x, closes, 1)[0]
    trend_pct = slope / closes[0] * 100 if closes[0] else 0

    # Volume trend: is volume increasing or decreasing?
    mid = len(volumes) // 2
    early_vol = np.mean(volumes[:mid]) if mid > 0 else 0
    late_vol = np.mean(volumes[mid:]) if volumes[mid:] else 0
    vol_trend = "increasing" if late_vol > early_vol * 1.1 else \
                "decreasing" if late_vol < early_vol * 0.9 else "stable"

    # Price range as % of open (volatility of session)
    session_range = (max(highs) - min(lows)) / closes[0] * 100 if closes[0] else 0

    # Last 3 candles direction
    recent_trend = "up" if closes[-1] > closes[-3] else \
                   "down" if closes[-1] < closes[-3] else "flat"

    # Classify momentum
    score = 0
    signals = []

    if trend_pct > 0.3:
        score += 2
        signals.append(f"📈 Intraday uptrend ({trend_pct:+.2f}% slope)")
    elif trend_pct < -0.3:
        score -= 2
        signals.append(f"📉 Intraday downtrend ({trend_pct:+.2f}% slope)")
    else:
        signals.append("➡️ Intraday sideways (no clear direction)")

    if vol_trend == "increasing" and trend_pct > 0:
        score += 1
        signals.append("✅ Volume rising with price — strong momentum")
    elif vol_trend == "increasing" and trend_pct < 0:
        score -= 1
        signals.append("⚠️ Volume rising on decline — selling pressure")
    elif vol_trend == "decreasing":
        signals.append("📉 Volume drying up — momentum fading")

    if recent_trend == "up":
        score += 1
        signals.append("🔼 Recent candles: bullish")
    elif recent_trend == "down":
        score -= 1
        signals.append("🔽 Recent candles: bearish")

    if score >= 2:
        label = "Strong Bullish Momentum"
        color = "green"
    elif score == 1:
        label = "Mild Bullish Momentum"
        color = "lightgreen"
    elif score == -1:
        label = "Mild Bearish Momentum"
        color = "orange"
    elif score <= -2:
        label = "Strong Bearish Momentum"
        color = "red"
    else:
        label = "Neutral / Sideways"
        color = "gray"

    return {
        "label": label,
        "color": color,
        "score": score,
        "trend_pct": round(trend_pct, 3),
        "volume_trend": vol_trend,
        "session_range_pct": round(session_range, 2),
        "signals": signals,
    }
