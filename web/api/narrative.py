"""
Daily Market Narrative Generator
==================================
Generates plain-English "what happened today" summaries.

Two modes:
1. Template-based (default, works without any API key)
   - Uses market data, regime, momentum, intraday moves
   - Produces clear, structured paragraph
   - Always available, zero cost

2. Claude AI-powered (optional, much better prose)
   - Pass ANTHROPIC_API_KEY env var to enable
   - Sends market data to Claude Haiku (fast + cheap)
   - Returns natural, analyst-style commentary
   - Falls back to template if API unavailable

The narrative answers these questions in plain English:
  - What did the market/stock do today?
  - Is the overall trend bullish or bearish?
  - What are the key signals saying?
  - What should I watch for next?
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(os.path.dirname(__file__)).parent.parent))


# ── Template-based Narrative ───────────────────────────────────────────────────

def build_template_narrative(data: dict) -> str:
    """
    Builds a structured plain-English summary from analysis data.
    No API required — pure logic from the numbers.
    """
    ticker = data.get("ticker", "")
    company = data.get("company_name", ticker)
    as_of = data.get("as_of", str(datetime.today().date()))
    regime = data.get("regime", {})
    metrics = data.get("metrics", {})
    performance = data.get("performance", {})
    intraday = data.get("intraday", {})
    intraday_mom = data.get("intraday_momentum", {})
    momentum = data.get("momentum_score", {})
    predictions = data.get("predictions", {})
    live = data.get("live_quote", {})
    currency = data.get("currency", "USD")
    sym = "₹" if currency == "INR" else "$"

    parts = []

    # ── Opening: What happened today ──
    price = metrics.get("price", 0)
    day_change = metrics.get("change_day", 0)
    intraday_change = intraday.get("intraday_change_pct", 0)

    if abs(day_change) >= 0.01:
        direction_word = "gained" if day_change > 0 else "declined"
        opening = (
            f"{company} ({ticker}) {direction_word} {abs(day_change):.2f}% today, "
            f"closing at {sym}{price:,.2f}."
        )
    else:
        opening = f"{company} ({ticker}) was largely unchanged today, trading around {sym}{price:,.2f}."

    if intraday.get("candle_count", 0) > 5:
        intraday_desc = (
            f" The stock opened at {sym}{intraday.get('open_price', 0):,.2f} "
            f"and reached an intraday high of {sym}{intraday.get('intraday_high', 0):,.2f} "
            f"with a low of {sym}{intraday.get('intraday_low', 0):,.2f}. "
            f"Total volume was {_fmt_volume(intraday.get('total_volume', 0))} shares."
        )
        opening += intraday_desc

    parts.append(opening)

    # ── Intraday momentum ──
    im_label = intraday_mom.get("label", "")
    im_signals = intraday_mom.get("signals", [])
    if im_label and im_signals:
        clean_signals = [s.replace("📈","").replace("📉","").replace("✅","").replace("⚠️","").replace("➡️","").strip()
                         for s in im_signals[:2]]
        parts.append(f"During today's session, momentum was {im_label.lower()}. {'. '.join(clean_signals)}.")

    # ── Broader trend / regime ──
    regime_name = regime.get("regime", "")
    regime_desc = regime.get("description", "")
    if regime_name:
        parts.append(
            f"Looking at the broader picture, {company} is currently in a {regime_name} regime. "
            f"{regime_desc}"
        )

    # ── Key indicator readings ──
    rsi = metrics.get("rsi", 50)
    rsi_label = metrics.get("rsi_label", "")
    macd_label = metrics.get("macd_label", "")
    vol_label = metrics.get("volume_label", "")
    annual_vol = metrics.get("volatility_annual", 0)

    indicator_parts = []
    if rsi_label:
        indicator_parts.append(f"RSI stands at {rsi:.0f} ({rsi_label.lower()})")
    if macd_label:
        indicator_parts.append(f"MACD shows a {macd_label.lower()}")
    if "Unusual" in vol_label or "Above Average" in vol_label:
        indicator_parts.append(f"volume is elevated at {vol_label.lower()}")

    if indicator_parts:
        parts.append(f"Key technical readings: {', '.join(indicator_parts)}. Annual volatility is {annual_vol:.1f}%.")

    # ── Momentum score ──
    m_score = momentum.get("score", 50)
    m_label = momentum.get("label", "")
    m_advice = momentum.get("advice", "")
    if m_label:
        parts.append(
            f"The composite momentum score is {m_score:.0f} out of 100 ({m_label}). {m_advice}"
        )

    # ── Price performance context ──
    chg_week = metrics.get("change_week", 0)
    chg_month = metrics.get("change_month", 0)
    chg_year = metrics.get("change_year", 0)

    perf_parts = []
    perf_parts.append(f"over the past week {_pct(chg_week)}")
    perf_parts.append(f"last month {_pct(chg_month)}")
    perf_parts.append(f"over the past year {_pct(chg_year)}")

    parts.append(f"In terms of price performance, {company} is {', '.join(perf_parts)}.")

    # ── Prediction outlook ──
    pred_1w = predictions.get("1_week", {})
    pred_1m = predictions.get("1_month", {})

    if pred_1w and not pred_1w.get("error"):
        d1w = pred_1w.get("direction", "Neutral")
        r1w = pred_1w.get("predicted_return_pct", 0)
        p1w = pred_1w.get("probability_up_pct", 50)
        b1w = pred_1w.get("price_base", 0)

        if pred_1m and not pred_1m.get("error"):
            d1m = pred_1m.get("direction", "Neutral")
            r1m = pred_1m.get("predicted_return_pct", 0)
            b1m = pred_1m.get("price_base", 0)
            outlook = (
                f"The AI model projects a {d1w.lower()} bias for the coming week "
                f"(base target: {sym}{b1w:,.2f}, probability of gain: {p1w:.0f}%) "
                f"and a {d1m.lower()} outlook for the month ahead "
                f"(base target: {sym}{b1m:,.2f})."
            )
        else:
            outlook = (
                f"The model projects a {d1w.lower()} bias for the coming week "
                f"with a base price target of {sym}{b1w:,.2f} and a {p1w:.0f}% probability of a positive return."
            )
        parts.append(outlook)

    # ── What to watch ──
    strategy = data.get("strategy", {})
    actions = strategy.get("actions", [])
    risk_level = strategy.get("risk_level", "Medium")
    if actions:
        clean = actions[0].replace("✅","").replace("⚠️","").replace("📈","").replace("📉","").replace("🛑","").replace("🔄","").replace("🎯","").replace("⏸️","").replace("⏳","").replace("🛡️","").strip()
        parts.append(f"Risk environment: {risk_level}. {clean}")

    # ── Closing ──
    parts.append(
        f"As always, this analysis is based on technical indicators and statistical patterns. "
        f"Macro events, earnings, and news can override any technical signal. "
        f"Use this as one input among many."
    )

    return " ".join(parts)


def _pct(val):
    v = float(val)
    return f"up {abs(v):.1f}%" if v > 0 else f"down {abs(v):.1f}%"

def _fmt_volume(v):
    if not v: return "—"
    if v >= 1e7: return f"{v/1e7:.1f} crore"
    if v >= 1e5: return f"{v/1e5:.1f} lakh"
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return str(int(v))


# ── Claude AI Narrative ────────────────────────────────────────────────────────

def build_ai_narrative(data: dict) -> str:
    """
    Uses Claude Haiku to generate a natural, analyst-quality narrative.
    Falls back to template if API key not set or call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return build_template_narrative(data)

    try:
        import anthropic

        ticker = data.get("ticker", "")
        company = data.get("company_name", ticker)
        regime = data.get("regime", {})
        metrics = data.get("metrics", {})
        momentum = data.get("momentum_score", {})
        intraday = data.get("intraday", {})
        predictions = data.get("predictions", {})
        currency = data.get("currency", "USD")
        sym = "₹" if currency == "INR" else "$"

        # Build a structured data summary for the prompt
        market_data = f"""
Stock: {company} ({ticker})
Date: {data.get('as_of', 'today')}
Current Price: {sym}{metrics.get('price', 0):,.2f}
Today's Change: {metrics.get('change_day', 0):+.2f}%
Week: {metrics.get('change_week', 0):+.2f}% | Month: {metrics.get('change_month', 0):+.2f}% | Year: {metrics.get('change_year', 0):+.2f}%

MARKET REGIME: {regime.get('regime', 'Unknown')}
Regime Description: {regime.get('description', '')}

TECHNICAL INDICATORS:
RSI: {metrics.get('rsi', 50):.1f} ({metrics.get('rsi_label', '')})
MACD: {metrics.get('macd_label', '')}
Bollinger Position: {metrics.get('bb_pct', 50):.1f}% ({metrics.get('bb_label', '')})
Annual Volatility: {metrics.get('volatility_annual', 0):.1f}%
Volume: {metrics.get('volume_label', '')}

MOMENTUM SCORE: {momentum.get('score', 50):.1f}/100 — {momentum.get('label', '')}
Breakdown: Trend={momentum.get('components', {}).get('trend', 50):.0f} | RSI={momentum.get('components', {}).get('rsi', 50):.0f} | MACD={momentum.get('components', {}).get('macd', 50):.0f}

INTRADAY SESSION:
Open: {sym}{intraday.get('open_price', 0):,.2f} | High: {sym}{intraday.get('intraday_high', 0):,.2f} | Low: {sym}{intraday.get('intraday_low', 0):,.2f}
Intraday Change: {intraday.get('intraday_change_pct', 0):+.2f}%
Session Momentum: {data.get('intraday_momentum', {}).get('label', 'N/A')}

AI PREDICTION:
1 Week: {predictions.get('1_week', {}).get('direction', 'N/A')} ({predictions.get('1_week', {}).get('predicted_return_pct', 0):+.1f}%, {predictions.get('1_week', {}).get('probability_up_pct', 50):.0f}% prob up)
1 Month: {predictions.get('1_month', {}).get('direction', 'N/A')} ({predictions.get('1_month', {}).get('predicted_return_pct', 0):+.1f}%)

STRATEGY: Risk Level {data.get('strategy', {}).get('risk_level', 'Medium')}
"""

        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": f"""You are a clear, plain-English market analyst writing for everyday investors — not finance professionals.

Based on this market data, write a 3-4 paragraph "What Happened Today" summary for {company}.

Rules:
- Write like you are explaining to a friend who invests but is not a finance expert
- No jargon without explanation. If you say RSI, say what it means in brackets
- Be direct about what is happening and what it means
- Do NOT give a buy/sell recommendation — describe the situation and signals
- Keep it factual and grounded in the data
- End with one sentence about what to watch next
- Total length: 150-200 words

Market Data:
{market_data}

Write the summary now:"""
            }]
        )

        return message.content[0].text.strip()

    except Exception as e:
        # Fall back to template if AI call fails
        return build_template_narrative(data)


# ── Market-wide Daily Summary ──────────────────────────────────────────────────

def build_market_summary() -> dict:
    """
    Generate a daily summary for key Indian and US indices.
    Called on dashboard load — gives the big picture.
    """
    import sys
    sys.path.insert(0, str(Path(os.path.dirname(__file__)).parent.parent))
    from web.api.analysis import analyze_ticker

    indices = [
        ("^NSEI",  "Nifty 50",  "🇮🇳"),
        ("^BSESN", "Sensex",    "🇮🇳"),
        ("SPY",    "S&P 500",   "🇺🇸"),
    ]

    results = []
    for ticker, name, flag in indices:
        try:
            data = analyze_ticker(ticker, period_years=1)
            d = data["metrics"]["change_day"]
            regime = data["regime"]["regime"]
            momentum = data["momentum_score"]["score"]
            price = data["metrics"]["price"]

            results.append({
                "ticker": ticker,
                "name": name,
                "flag": flag,
                "price": price,
                "change_day": d,
                "regime": regime,
                "regime_color": data["regime"]["color"],
                "momentum_score": momentum,
                "momentum_label": data["momentum_score"]["label"],
            })
        except Exception as e:
            results.append({
                "ticker": ticker,
                "name": name,
                "flag": flag,
                "error": str(e),
            })

    # Overall market mood
    valid = [r for r in results if "change_day" in r]
    if valid:
        avg_change = sum(r["change_day"] for r in valid) / len(valid)
        avg_momentum = sum(r["momentum_score"] for r in valid) / len(valid)

        if avg_momentum >= 65:
            mood = "Risk-On 🟢"
            mood_desc = "Most major indices are trending up with positive momentum."
        elif avg_momentum >= 45:
            mood = "Mixed ⚡"
            mood_desc = "Markets are sending mixed signals — some indices positive, others negative."
        else:
            mood = "Risk-Off 🔴"
            mood_desc = "Broad selling pressure across major indices. Caution advised."
    else:
        mood = "—"
        mood_desc = "Could not fetch index data."
        avg_change = 0

    return {
        "indices": results,
        "overall_mood": mood,
        "mood_description": mood_desc,
        "as_of": str(datetime.now().strftime("%d %b %Y, %H:%M")),
    }
