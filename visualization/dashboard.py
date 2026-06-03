"""
Interactive visualization dashboard using Plotly.

Generates HTML files (no server needed — open in any browser):
1. Portfolio curves: all agents + buy-and-hold on same chart
2. Trade overlay: price chart with buy/sell markers per agent
3. Training curves: episode reward progression per agent
4. Strategy comparison: bar charts of key metrics side-by-side
5. Drawdown chart: underwater curve showing risk periods

Why Plotly over matplotlib:
- Interactive: hover for values, zoom into periods, toggle agents on/off
- HTML output: shareable without a Python environment
- Professional look for portfolio presentations
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import pandas as pd
import numpy as np
import pickle
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
VIZ_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "charts")

AGENT_COLORS = {
    "agent_0": "#636EFA",  # Blue
    "agent_1": "#EF553B",  # Red
    "agent_2": "#00CC96",  # Green
    "buy_and_hold": "#FFA15A",  # Orange
}

STRATEGY_LABELS = {
    "momentum": "Momentum",
    "mean_reversion": "Mean Reversion",
    "market_making": "Market Making",
    "passive_hold": "Passive Hold",
    "mixed": "Mixed",
    "unknown": "Unknown",
}


def load_results():
    path = os.path.join(RESULTS_DIR, "backtest_results.pkl")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No backtest results at {path}. Run evaluation first.")
    with open(path, "rb") as f:
        return pickle.load(f)


def load_episode_history():
    path = os.path.join(RESULTS_DIR, "episode_history.pkl")
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def portfolio_curves_chart(results: dict) -> go.Figure:
    """
    Line chart: portfolio value over time for all agents + benchmark.
    Normalized to % return so agents start at the same baseline.
    """
    fig = go.Figure()

    agent_names = [k for k in results.keys() if k != "buy_and_hold"]

    for agent_name in agent_names + ["buy_and_hold"]:
        if agent_name not in results:
            continue
        pv = np.array(results[agent_name]["portfolio_history"])
        pct_return = (pv / pv[0] - 1) * 100

        strategy = results[agent_name].get("strategy", {}).get("strategy", "")
        label = f"{agent_name} ({STRATEGY_LABELS.get(strategy, strategy)})" if strategy else agent_name
        if agent_name == "buy_and_hold":
            label = "Buy & Hold (SPY)"

        color = AGENT_COLORS.get(agent_name, "#888")
        dash = "dot" if agent_name == "buy_and_hold" else "solid"

        fig.add_trace(go.Scatter(
            y=pct_return,
            name=label,
            line=dict(color=color, width=2, dash=dash),
            hovertemplate=f"<b>{label}</b><br>Return: %{{y:.2f}}%<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="Portfolio Returns — Test Set (2023-2024)",
        xaxis_title="Trading Days",
        yaxis_title="Cumulative Return (%)",
        hovermode="x unified",
        template="plotly_dark",
        legend=dict(x=0.01, y=0.99),
        height=500,
    )
    return fig


def trade_overlay_chart(results: dict) -> go.Figure:
    """
    Price chart with buy/sell trade markers overlaid per agent.
    Makes emergent strategies visually obvious:
    - Momentum traders cluster buys at breakouts
    - Mean-reversion traders buy at dips
    """
    agent_names = [k for k in results.keys() if k != "buy_and_hold" and "action_log" in results[k]]
    if not agent_names:
        return go.Figure()

    # Use first agent's log for price
    prices = [d["price"] for d in results[agent_names[0]]["action_log"]]

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        y=prices,
        name="SPY Price",
        line=dict(color="#888", width=1),
        opacity=0.7,
    ))

    for agent_name in agent_names:
        action_log = results[agent_name].get("action_log", [])
        strategy = results[agent_name].get("strategy", {}).get("strategy", "")
        color = AGENT_COLORS.get(agent_name, "#888")

        buys = [(d["step"], d["price"]) for d in action_log if d["action"] == 1]
        sells = [(d["step"], d["price"]) for d in action_log if d["action"] == 2]

        label_base = f"{agent_name} ({STRATEGY_LABELS.get(strategy, '')})"

        if buys:
            bx, by = zip(*buys)
            fig.add_trace(go.Scatter(
                x=list(bx), y=list(by),
                mode="markers",
                name=f"{label_base} BUY",
                marker=dict(symbol="triangle-up", size=8, color=color, opacity=0.8),
            ))
        if sells:
            sx, sy = zip(*sells)
            fig.add_trace(go.Scatter(
                x=list(sx), y=list(sy),
                mode="markers",
                name=f"{label_base} SELL",
                marker=dict(symbol="triangle-down", size=8, color=color, opacity=0.8,
                            line=dict(width=1, color="white")),
            ))

    fig.update_layout(
        title="Trade Decisions Overlaid on Price Chart",
        xaxis_title="Trading Days",
        yaxis_title="Price ($)",
        template="plotly_dark",
        height=600,
    )
    return fig


def metrics_comparison_chart(results: dict) -> go.Figure:
    """Bar chart comparing key financial metrics across agents."""
    metrics_to_show = ["sharpe_ratio", "sortino_ratio", "total_return_pct", "max_drawdown", "cagr_pct"]
    metric_labels = ["Sharpe Ratio", "Sortino Ratio", "Total Return %", "Max Drawdown %", "CAGR %"]

    agent_names = list(results.keys())
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=metric_labels + ["Win Rate %"],
        specs=[[{}, {}, {}], [{}, {}, {}]],
    )

    positions = [(1,1), (1,2), (1,3), (2,1), (2,2), (2,3)]

    for idx, (metric, label) in enumerate(zip(metrics_to_show, metric_labels)):
        row, col = positions[idx]
        vals = [results[a]["metrics"].get(metric, 0) for a in agent_names]
        colors = [AGENT_COLORS.get(a, "#888") for a in agent_names]

        fig.add_trace(
            go.Bar(
                x=agent_names,
                y=vals,
                marker_color=colors,
                name=label,
                showlegend=False,
                text=[f"{v:.2f}" for v in vals],
                textposition="auto",
            ),
            row=row, col=col,
        )

    # Win rate
    win_rates = [results[a]["metrics"].get("win_rate_pct", 0) for a in agent_names]
    fig.add_trace(
        go.Bar(
            x=agent_names,
            y=win_rates,
            marker_color=[AGENT_COLORS.get(a, "#888") for a in agent_names],
            name="Win Rate",
            showlegend=False,
            text=[f"{v:.1f}%" for v in win_rates],
            textposition="auto",
        ),
        row=2, col=3,
    )

    fig.update_layout(
        title="Performance Metrics Comparison",
        template="plotly_dark",
        height=600,
    )
    return fig


def drawdown_chart(results: dict) -> go.Figure:
    """Underwater equity curve — shows when and how deep each agent went into drawdown."""
    fig = go.Figure()

    for agent_name, data in results.items():
        pv = np.array(data["portfolio_history"])
        cumulative = pv / pv[0]
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max * 100

        color = AGENT_COLORS.get(agent_name, "#888")
        strategy = data.get("strategy", {}).get("strategy", "")
        label = f"{agent_name} ({STRATEGY_LABELS.get(strategy, strategy)})" if strategy else agent_name

        fig.add_trace(go.Scatter(
            y=drawdown,
            name=label,
            fill="tozeroy",
            line=dict(color=color, width=1),
            fillcolor=color.replace(")", ", 0.2)").replace("rgb", "rgba") if color.startswith("rgb") else color,
            opacity=0.6,
        ))

    fig.add_hline(y=0, line_color="white", opacity=0.3)
    fig.update_layout(
        title="Drawdown Chart (Underwater Equity Curve)",
        xaxis_title="Trading Days",
        yaxis_title="Drawdown (%)",
        template="plotly_dark",
        hovermode="x unified",
        height=400,
    )
    return fig


def training_curves_chart(episode_history: list) -> go.Figure:
    """Shows portfolio value per agent across training episodes — convergence/divergence."""
    if not episode_history:
        return go.Figure()

    df = pd.DataFrame(episode_history)
    fig = go.Figure()

    for i in range(3):
        col = f"agent_{i}_portfolio_value"
        if col not in df.columns:
            continue
        # Smooth with rolling average
        smoothed = df[col].rolling(20, min_periods=1).mean()
        color = AGENT_COLORS.get(f"agent_{i}", "#888")
        fig.add_trace(go.Scatter(
            x=df["episode"],
            y=smoothed,
            name=f"agent_{i}",
            line=dict(color=color, width=2),
        ))

    fig.add_hline(y=10000, line_dash="dash", line_color="gray", opacity=0.5,
                  annotation_text="Initial Capital")

    fig.update_layout(
        title="Training Progress — Episode Portfolio Value (20-ep rolling avg)",
        xaxis_title="Episode",
        yaxis_title="Portfolio Value ($)",
        template="plotly_dark",
        height=450,
    )
    return fig


def strategy_radar_chart(results: dict) -> go.Figure:
    """Radar chart comparing strategy characteristics across agents."""
    categories = ["Trade Freq", "Buy/Sell Balance", "Buy Momentum", "Sharpe", "Total Return"]

    agent_names = [k for k in results.keys() if k != "buy_and_hold"]
    fig = go.Figure()

    for agent_name in agent_names:
        strat = results[agent_name].get("strategy", {})
        metrics = results[agent_name].get("metrics", {})
        color = AGENT_COLORS.get(agent_name, "#888")

        vals = [
            strat.get("trade_frequency", 0) * 5,  # scale to ~0-1
            strat.get("buy_sell_balance", 0.5),
            max(0, strat.get("avg_buy_momentum", 0) * 100 + 0.5),  # center at 0.5
            max(0, min(2, metrics.get("sharpe_ratio", 0) + 1)) / 2,  # normalize
            max(0, min(1, (metrics.get("total_return_pct", 0) + 50) / 100)),
        ]

        strategy = strat.get("strategy", "")
        label = f"{agent_name} ({STRATEGY_LABELS.get(strategy, strategy)})"

        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=categories + [categories[0]],
            name=label,
            fill="toself",
            line=dict(color=color),
            opacity=0.6,
        ))

    fig.update_layout(
        title="Strategy Profile Comparison (Radar)",
        polar=dict(radialaxis=dict(range=[0, 1])),
        template="plotly_dark",
        height=500,
    )
    return fig


def generate_all_charts(output_dir: str = None):
    """Generate and save all charts as interactive HTML files."""
    if output_dir is None:
        output_dir = VIZ_DIR
    os.makedirs(output_dir, exist_ok=True)

    results = load_results()
    episode_history = load_episode_history()

    charts = [
        ("portfolio_curves.html", "Portfolio Return Curves", portfolio_curves_chart(results)),
        ("trade_overlay.html", "Trade Decisions on Price", trade_overlay_chart(results)),
        ("metrics_comparison.html", "Metrics Comparison", metrics_comparison_chart(results)),
        ("drawdown.html", "Drawdown Analysis", drawdown_chart(results)),
        ("strategy_radar.html", "Strategy Profile Radar", strategy_radar_chart(results)),
    ]

    if episode_history:
        charts.append(("training_curves.html", "Training Progress", training_curves_chart(episode_history)))

    saved = []
    for filename, title, fig in charts:
        path = os.path.join(output_dir, filename)
        fig.write_html(path)
        saved.append(path)
        print(f"  Saved: {path}")

    # Combined dashboard
    combined_path = os.path.join(output_dir, "dashboard.html")
    with open(combined_path, "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
<title>Multi-Agent RL Trading Dashboard</title>
<style>
  body { background: #1a1a2e; color: #eee; font-family: monospace; margin: 0; padding: 20px; }
  h1 { color: #636EFA; text-align: center; }
  h2 { color: #aaa; margin-top: 30px; }
  iframe { width: 100%; border: 1px solid #333; margin-bottom: 20px; }
</style>
</head>
<body>
<h1>Multi-Agent RL Trading System — Results Dashboard</h1>
""")
        for filename, title, _ in charts:
            f.write(f'<h2>{title}</h2>\n')
            f.write(f'<iframe src="{filename}" height="550" frameborder="0"></iframe>\n')
        f.write("</body></html>")

    print(f"\nCombined dashboard: {combined_path}")
    return saved


if __name__ == "__main__":
    generate_all_charts()
