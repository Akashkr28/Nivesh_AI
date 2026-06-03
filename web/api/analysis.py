"""
Core analysis engine for the web API.
Wraps the existing pipeline (data download, indicators, backtest metrics)
into simple functions that return JSON-serializable results.

No training required for web users — analysis is purely indicator-based
and runs in under 10 seconds for any ticker.
"""

import sys
import os
import numpy as np
import pandas as pd
import yfinance as yf
import ta
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Data Fetching ──────────────────────────────────────────────────────────────

def fetch_stock_data(ticker: str, period_years: int = 3, resolved_ticker: str = None) -> tuple:
    """
    Always fetch max(period_years, 1.5) + 1 extra year for indicator warmup.
    Returns (full_df_for_indicators, display_df trimmed to period_years).
    The 200-day SMA needs ~200 rows before it's valid — so we always
    pull at least 1 extra year of data, compute indicators on the full set,
    then trim the display window to what the user requested.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from web.api.india_stocks import fetch_with_fallback, is_indian_ticker

    # Use resolved ticker if provided, else use raw ticker
    fetch_ticker = resolved_ticker or ticker

    end = datetime.today()
    start_display = end - timedelta(days=period_years * 365)

    if is_indian_ticker(fetch_ticker):
        # Use Indian fallback-aware fetch
        df, actual_ticker = fetch_with_fallback(fetch_ticker, period_years)
    else:
        fetch_years = max(period_years + 1, 2)
        start_full = end - timedelta(days=fetch_years * 365)
        df = yf.download(fetch_ticker, start=start_full.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"), auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.names = [None]
        df.dropna(inplace=True)
        actual_ticker = fetch_ticker

    if df is None or df.empty or len(df) < 10:
        raise ValueError(
            f"No data found for '{ticker}'. "
            f"For Indian stocks try: RELIANCE.NS, HDFCBANK.NS, TCS.NS. "
            f"For US stocks try: AAPL, TSLA, NVDA."
        )
    if len(df) < 30:
        raise ValueError(f"'{ticker}' has only {len(df)} trading days — too short to analyze.")

    df_display = df[df.index >= pd.Timestamp(start_display)].copy()
    return df, df_display


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Ensure clean column names (yfinance sometimes leaves 'Price' as level name)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns.names = [None]

    n = len(df)
    # Adaptive windows — shorter for newly listed stocks with limited history
    rsi_w  = min(14, max(5, n // 10))
    macd_s, macd_l, macd_sig = (min(12,n//10), min(26,n//5), min(9,n//12))
    bb_w   = min(20, max(10, n // 10))
    sma_s  = min(20, max(5,  n // 10))
    sma_l  = min(50, max(10, n // 5))
    atr_w  = min(14, max(5,  n // 10))
    vol_w  = min(20, max(5,  n // 10))

    df["rsi"] = ta.momentum.RSIIndicator(df["Close"], window=rsi_w).rsi()

    macd = ta.trend.MACD(df["Close"], window_slow=macd_l, window_fast=macd_s, window_sign=macd_sig)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"] = macd.macd_diff()

    bb = ta.volatility.BollingerBands(df["Close"], window=bb_w, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_pct"] = bb.bollinger_pband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    df["atr"] = ta.volatility.AverageTrueRange(
        df["High"], df["Low"], df["Close"], window=atr_w).average_true_range()

    df["sma_20"] = df["Close"].rolling(sma_s).mean()
    df["sma_50"] = df["Close"].rolling(sma_l).mean()
    df["sma_200"] = df["Close"].rolling(min(200, max(50, n // 2))).mean()

    df["returns"] = df["Close"].pct_change()
    df["volatility_20"] = df["returns"].rolling(vol_w).std() * np.sqrt(252)
    df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(vol_w).mean()

    df.dropna(inplace=True)
    return df


# ── Regime Detection ───────────────────────────────────────────────────────────

def detect_regime(df: pd.DataFrame) -> dict:
    """
    Classify current market regime using multiple signals.
    Returns a regime label + confidence + plain-English explanation.
    """
    latest = df.iloc[-1]
    price = float(latest["Close"])
    sma20 = float(latest["sma_20"])
    sma50 = float(latest["sma_50"])
    sma200 = float(latest.get("sma_200", price))
    rsi = float(latest["rsi"])
    vol = float(latest["volatility_20"])
    avg_vol = float(df["volatility_20"].mean())
    bb_pct = float(latest["bb_pct"])

    signals = []
    score = 0  # positive = bullish, negative = bearish

    # Trend signals
    if price > sma20 > sma50:
        score += 2
        signals.append("Price above short & medium moving averages (uptrend)")
    elif price < sma20 < sma50:
        score -= 2
        signals.append("Price below short & medium moving averages (downtrend)")

    if price > sma200:
        score += 1
        signals.append("Price above 200-day average (long-term bullish)")
    else:
        score -= 1
        signals.append("Price below 200-day average (long-term bearish)")

    # Momentum signals
    if rsi > 70:
        signals.append(f"RSI {rsi:.0f} — Overbought (potential pullback)")
        score -= 1
    elif rsi < 30:
        signals.append(f"RSI {rsi:.0f} — Oversold (potential bounce)")
        score += 1
    elif rsi > 55:
        signals.append(f"RSI {rsi:.0f} — Bullish momentum")
        score += 1
    elif rsi < 45:
        signals.append(f"RSI {rsi:.0f} — Bearish momentum")
        score -= 1

    # Volatility
    high_vol = vol > avg_vol * 1.3
    if high_vol:
        signals.append(f"Volatility elevated ({vol*100:.1f}% annualized) — uncertain conditions")

    # Classify
    if high_vol and score < 0:
        regime = "Bear + High Volatility"
        color = "red"
        description = "Market is in a downtrend with elevated volatility. High-risk environment. Defensive positioning recommended."
        strategy_tip = "Mean-reversion strategies tend to perform here — buy panic dips, sell relief rallies."
    elif high_vol and score >= 0:
        regime = "Transitional / High Volatility"
        color = "orange"
        description = "Mixed signals with high volatility. Market is uncertain and difficult to trade directionally."
        strategy_tip = "Reduce position size. Wait for clearer direction before committing."
    elif score >= 3:
        regime = "Strong Bull"
        color = "green"
        description = "Clear uptrend across multiple timeframes. Momentum is strong and sustained."
        strategy_tip = "Momentum strategies work best here — trend following, buy breakouts, hold positions."
    elif score >= 1:
        regime = "Mild Bull"
        color = "lightgreen"
        description = "Moderate uptrend. Market is positive but not strongly trending."
        strategy_tip = "Light momentum bias. Consider partial positions and tighter stops."
    elif score <= -3:
        regime = "Strong Bear"
        color = "red"
        description = "Clear downtrend. Multiple indicators confirm negative momentum."
        strategy_tip = "Mean-reversion or cash. Avoid momentum buying until trend reverses."
    else:
        regime = "Sideways / Ranging"
        color = "gray"
        description = "No clear trend. Price oscillating around moving averages."
        strategy_tip = "Mean-reversion strategies shine here — buy oversold, sell overbought within the range."

    return {
        "regime": regime,
        "color": color,
        "description": description,
        "strategy_tip": strategy_tip,
        "signals": signals,
        "score": score,
    }


# ── Key Metrics ────────────────────────────────────────────────────────────────

def compute_metrics(df: pd.DataFrame) -> dict:
    """Current snapshot metrics in plain-English ranges."""
    latest = df.iloc[-1]
    price = float(latest["Close"])
    prev_close = float(df.iloc[-2]["Close"])
    week_ago = float(df.iloc[-5]["Close"]) if len(df) >= 5 else price
    month_ago = float(df.iloc[-21]["Close"]) if len(df) >= 21 else price
    year_ago = float(df.iloc[-252]["Close"]) if len(df) >= 252 else price

    rsi = float(latest["rsi"])
    bb_pct = float(latest["bb_pct"]) * 100

    if rsi >= 70:
        rsi_label = "Overbought"
        rsi_color = "red"
    elif rsi <= 30:
        rsi_label = "Oversold"
        rsi_color = "green"
    elif rsi >= 55:
        rsi_label = "Bullish"
        rsi_color = "lightgreen"
    elif rsi <= 45:
        rsi_label = "Bearish"
        rsi_color = "orange"
    else:
        rsi_label = "Neutral"
        rsi_color = "gray"

    if bb_pct >= 80:
        bb_label = "Near Upper Band (overbought)"
        bb_color = "red"
    elif bb_pct <= 20:
        bb_label = "Near Lower Band (oversold)"
        bb_color = "green"
    else:
        bb_label = "Inside Bands (neutral)"
        bb_color = "gray"

    macd_diff = float(latest["macd_diff"])
    if macd_diff > 0:
        macd_label = "Bullish Crossover"
        macd_color = "green"
    else:
        macd_label = "Bearish Crossover"
        macd_color = "red"

    vol_ratio = float(latest["volume_ratio"]) if not pd.isna(latest["volume_ratio"]) else 1.0
    if vol_ratio > 1.5:
        vol_label = f"{vol_ratio:.1f}x avg — Unusual Activity"
        vol_color = "orange"
    elif vol_ratio > 1.1:
        vol_label = f"{vol_ratio:.1f}x avg — Above Average"
        vol_color = "lightgreen"
    else:
        vol_label = f"{vol_ratio:.1f}x avg — Normal"
        vol_color = "gray"

    return {
        "price": round(price, 2),
        "change_day": round((price - prev_close) / prev_close * 100, 2),
        "change_week": round((price - week_ago) / week_ago * 100, 2),
        "change_month": round((price - month_ago) / month_ago * 100, 2),
        "change_year": round((price - year_ago) / year_ago * 100, 2),
        "rsi": round(rsi, 1),
        "rsi_label": rsi_label,
        "rsi_color": rsi_color,
        "bb_pct": round(bb_pct, 1),
        "bb_label": bb_label,
        "bb_color": bb_color,
        "macd_label": macd_label,
        "macd_color": macd_color,
        "volume_label": vol_label,
        "volume_color": vol_color,
        "atr": round(float(latest["atr"]), 2),
        "volatility_annual": round(float(latest["volatility_20"]) * 100, 1),
    }


# ── Chart Data ─────────────────────────────────────────────────────────────────

def build_chart_data(df: pd.DataFrame) -> dict:
    """Build chart series from the display-trimmed dataframe (already period-filtered)."""
    display = df.copy()
    dates = [str(d.date()) for d in display.index]

    def safe_list(series):
        return [round(float(v), 4) if not pd.isna(v) else None for v in series]

    return {
        "dates": dates,
        "price": safe_list(display["Close"]),
        "sma20": safe_list(display["sma_20"]),
        "sma50": safe_list(display["sma_50"]),
        "bb_upper": safe_list(display["bb_upper"]),
        "bb_lower": safe_list(display["bb_lower"]),
        "bb_mid": safe_list(display["bb_mid"]),
        "volume": safe_list(display["Volume"]),
        "rsi": safe_list(display["rsi"]),
        "macd": safe_list(display["macd"]),
        "macd_signal": safe_list(display["macd_signal"]),
        "macd_diff": safe_list(display["macd_diff"]),
    }


# ── Strategy Recommendation ────────────────────────────────────────────────────

def get_strategy_recommendation(regime: dict, metrics: dict) -> dict:
    """
    Plain-English recommendation based on regime + current indicators.
    This is the output a non-technical user actually reads.
    """
    rsi = metrics["rsi"]
    bb_pct = metrics["bb_pct"]
    regime_name = regime["regime"]
    change_month = metrics["change_month"]

    actions = []
    risk_level = "Medium"

    if "Bull" in regime_name:
        if rsi < 60 and bb_pct < 60:
            actions.append("✅ Conditions are positive — trend is up and not overbought yet")
            actions.append("📈 Momentum favors holding or adding to long positions")
            risk_level = "Low-Medium"
        elif rsi > 70:
            actions.append("⚠️ Trend is up but RSI shows overbought — wait for a pullback to enter")
            actions.append("📊 Existing positions: consider partial profit-taking")
            risk_level = "Medium"
        else:
            actions.append("📈 Moderate uptrend — trend followers likely doing well here")
            risk_level = "Medium"

    elif "Bear" in regime_name:
        if rsi < 35:
            actions.append("🔄 Oversold in a downtrend — short-term bounce possible but trend is down")
            actions.append("⚠️ Counter-trend bounces are risky — keep position sizes small")
        else:
            actions.append("🛑 Downtrend confirmed — momentum strategies are losing money here")
            actions.append("🔄 Mean-reversion strategy: wait for RSI < 30 before considering entry")
        risk_level = "High"

    elif "Sideways" in regime_name or "Ranging" in regime_name:
        if bb_pct < 20:
            actions.append("🔄 Price near lower Bollinger Band in a ranging market — mean-reversion opportunity")
            actions.append("🎯 Range-trading: buy near lower band, target the middle band")
        elif bb_pct > 80:
            actions.append("🔄 Price near upper Bollinger Band in a ranging market — potential short-term top")
            actions.append("🎯 Range-trading: sell/reduce near upper band, target the middle band")
        else:
            actions.append("⏸️ No clear edge — market is ranging with price in the middle of its band")
            actions.append("⏳ Best action: wait for price to reach band extremes or trend to emerge")
        risk_level = "Medium"

    else:
        actions.append("⚠️ Mixed signals — high volatility makes direction uncertain")
        actions.append("🛡️ Reduce exposure until market stabilizes")
        risk_level = "High"

    risk_colors = {"Low": "green", "Low-Medium": "lightgreen",
                   "Medium": "orange", "High": "red"}

    return {
        "actions": actions,
        "risk_level": risk_level,
        "risk_color": risk_colors.get(risk_level, "orange"),
        "summary": f"{regime_name} regime — {risk_level} risk environment",
    }


# ── Historical Performance ─────────────────────────────────────────────────────

def compute_historical_performance(df: pd.DataFrame) -> dict:
    """Sharpe, drawdown, win rate on the historical data shown."""
    returns = df["returns"].dropna()
    if len(returns) < 20:
        return {}

    ann = np.sqrt(252)
    sharpe = (returns.mean() / (returns.std() + 1e-10)) * ann
    sortino_denom = returns[returns < 0].std() + 1e-10
    sortino = (returns.mean() / sortino_denom) * ann

    cumret = (1 + returns).cumprod()
    running_max = cumret.cummax()
    drawdown = (cumret - running_max) / running_max
    max_dd = float(drawdown.min()) * 100

    total_return = float((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100)
    win_rate = float((returns > 0).mean() * 100)

    n_years = len(returns) / 252
    cagr = float(((1 + total_return / 100) ** (1 / max(n_years, 0.1)) - 1) * 100) if total_return > -100 else -100.0

    return {
        "sharpe": round(float(sharpe), 2),
        "sortino": round(float(sortino), 2),
        "max_drawdown": round(max_dd, 1),
        "total_return": round(total_return, 1),
        "cagr": round(cagr, 1),
        "win_rate": round(win_rate, 1),
        "period_days": len(returns),
    }


# ── Master Analysis Function ───────────────────────────────────────────────────

def analyze_ticker(ticker: str, period_years: int = 3) -> dict:
    """Single entry point called by the API endpoint."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from web.api.realtime import get_live_quote, get_intraday_data, compute_intraday_momentum, get_market_status, detect_market
    from web.api.prediction import generate_predictions, compute_momentum_score

    from web.api.india_stocks import resolve_indian_ticker, is_indian_ticker

    ticker = ticker.upper().strip()

    # Resolve Indian stocks to correct Yahoo Finance symbol.
    # Only apply Indian resolution if ticker looks Indian (has .NS/.BO, is a known index,
    # or is in the override table). US tickers like AAPL, NVDA stay as-is.
    from web.api.india_stocks import SYMBOL_OVERRIDES
    looks_indian = (
        is_indian_ticker(ticker) or
        ticker in SYMBOL_OVERRIDES or
        ticker.upper() in SYMBOL_OVERRIDES
    )
    resolved = resolve_indian_ticker(ticker) if looks_indian else ticker

    # df_full: full history for indicator warmup (always 2+ years)
    # df_display: trimmed to user-requested period for charts
    df_full, df_display = fetch_stock_data(ticker, period_years, resolved_ticker=resolved)
    df_full = add_indicators(df_full)

    # Propagate indicators to display slice (they share the same index)
    indicator_cols = [c for c in df_full.columns if c not in ["Open","High","Low","Close","Volume"]]
    for col in indicator_cols:
        if col not in df_display.columns:
            df_display[col] = df_full[col]
    df_display = df_display.dropna(subset=["rsi"])  # drop warmup rows from display

    # All analysis runs on full df (more data = better signals), charts use display df
    regime = detect_regime(df_full)
    metrics = compute_metrics(df_full)
    chart_data = build_chart_data(df_display)
    strategy = get_strategy_recommendation(regime, metrics)
    performance = compute_historical_performance(df_display)

    # ── New: Real-time & prediction data ──
    live_quote = get_live_quote(ticker)
    market_status = get_market_status(ticker)
    intraday = get_intraday_data(ticker, interval="15m")
    intraday_momentum = compute_intraday_momentum(intraday)
    predictions = generate_predictions(df_full, live_quote.get("price") or metrics["price"])
    momentum_score = compute_momentum_score(df_full)

    # Get company name
    try:
        info = yf.Ticker(ticker).info
        company_name = info.get("longName", ticker)
        sector = info.get("sector", "—")
        exchange = info.get("exchange", "—")
        currency = info.get("currency", "USD")
        market_cap = info.get("marketCap", None)
        if market_cap:
            if market_cap >= 1e12:
                market_cap_str = f"${market_cap/1e12:.1f}T"
            elif market_cap >= 1e9:
                market_cap_str = f"${market_cap/1e9:.1f}B"
            else:
                market_cap_str = f"${market_cap/1e6:.0f}M"
        else:
            market_cap_str = "—"
    except Exception:
        company_name = ticker
        sector = "—"
        exchange = "—"
        currency = "INR" if detect_market(ticker) == "IN" else "USD"
        market_cap_str = "—"

    # Override price with live quote if available
    if live_quote.get("price") and live_quote["price"] > 0:
        metrics["price"] = live_quote["price"]
        metrics["change_day"] = live_quote["change_pct"]

    return {
        "ticker": ticker,
        "company_name": company_name,
        "sector": sector,
        "exchange": exchange,
        "currency": currency,
        "market_cap": market_cap_str,
        "as_of": str(df_full.index[-1].date()),
        "market_status": market_status,
        "live_quote": live_quote,
        "regime": regime,
        "metrics": metrics,
        "strategy": strategy,
        "performance": performance,
        "chart_data": chart_data,
        "intraday": intraday,
        "intraday_momentum": intraday_momentum,
        "predictions": predictions,
        "momentum_score": momentum_score,
    }
