"""
Backtesting and evaluation module.

Runs trained agents on the held-out test set (2023-2024) and computes:
1. Financial metrics via quantstats: Sharpe, Sortino, Max Drawdown, CAGR
2. Strategy classification: did agents learn momentum, mean-reversion, or
   market-making strategies? (the core multi-agent research finding)
3. Agent comparison: did identical architectures diverge into different strategies?

Strategy classification logic:
- Momentum: agent tends to BUY after positive recent returns, SELL after negative
  (autocorrelation of action with recent price trend > 0)
- Mean-reversion: opposite — BUY when oversold (low RSI), SELL when overbought
  (negative correlation between RSI and buy probability)
- Market-making: frequent trading regardless of direction (high trade count,
  lower directional bias)
"""

import numpy as np
import pandas as pd
import torch
import os
import sys
import pickle
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.policy_network import TradingActorCritic
from envs.trading_env import (
    MultiAgentTradingEnv, FEATURE_COLS, INITIAL_CASH, SHARES_PER_TRADE,
    TRANSACTION_COST, MAX_SHARES
)

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def load_agents(checkpoint_dir: str, num_agents: int, obs_dim: int):
    """Load final trained policy weights for all agents."""
    agents = {}
    for i in range(num_agents):
        policy = TradingActorCritic(obs_dim).to(DEVICE)
        path = os.path.join(checkpoint_dir, f"agent_{i}_final.pt")
        if os.path.exists(path):
            ckpt = torch.load(path, map_location=DEVICE, weights_only=False)
            policy.load_state_dict(ckpt["policy_state"])
            policy.eval()
            print(f"Loaded agent_{i} from {path}")
        else:
            print(f"WARNING: No checkpoint found at {path}, using random policy")
        agents[f"agent_{i}"] = policy
    return agents


@torch.no_grad()
def run_backtest(
    agents_policies: dict,
    num_agents: int = 3,
    episode_length: int = None,
):
    """
    Run a full backtest on the test set.
    Returns per-agent portfolio histories and trade logs.
    """
    env = MultiAgentTradingEnv(num_agents=num_agents, split="test", episode_length=500)

    # Override: use full test set
    env.start_idx = 0
    if episode_length is None:
        env.episode_length = len(env.prices) - 1
    else:
        env.episode_length = episode_length

    obs_dim = env.observation_space("agent_0").shape[0]
    observations, _ = env.reset()
    # Override start again after reset
    env.start_idx = 0

    portfolio_histories = {a: [INITIAL_CASH] for a in env.possible_agents}
    trade_logs = {a: [] for a in env.possible_agents}
    action_logs = {a: [] for a in env.possible_agents}

    last_obs = {a: observations.get(a, np.zeros(obs_dim)) for a in env.possible_agents}

    step = 0
    max_steps = len(env.prices) - 2

    while step < max_steps and len(env.agents) > 0:
        agent_name = env.agent_selection

        obs = last_obs[agent_name]
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(DEVICE)

        if agent_name in agents_policies:
            action, _, _, _ = agents_policies[agent_name].get_action_and_value(obs_t)
            action = action.item()
        else:
            action = 1  # default BUY for random baseline

        env.step(action)
        next_obs = env.observe(agent_name)
        if next_obs is None:
            next_obs = np.zeros(obs_dim, dtype=np.float32)
        last_obs[agent_name] = next_obs

        price = env._current_price()
        pv = env._portfolio_value(agent_name, price)
        portfolio_histories[agent_name].append(pv)

        action_logs[agent_name].append({
            "step": step,
            "action": action,
            "price": price,
            "shares": env.shares[agent_name],
            "portfolio_value": pv,
        })

        done = env.terminations.get(agent_name, False) or env.truncations.get(agent_name, False)
        if done:
            break

        step += 1

    env.close()
    return portfolio_histories, action_logs


def compute_financial_metrics(portfolio_values: list, benchmark_prices: pd.Series = None):
    """
    Compute standard financial performance metrics.

    - Sharpe Ratio: risk-adjusted return. >1 is acceptable, >2 is strong
    - Sortino Ratio: like Sharpe but only penalizes downside volatility
    - Max Drawdown: worst peak-to-trough decline (lower is better)
    - CAGR: Compound Annual Growth Rate
    - Calmar Ratio: CAGR / Max Drawdown
    """
    pv = np.array(portfolio_values, dtype=np.float64)
    returns = np.diff(pv) / pv[:-1]

    if len(returns) == 0:
        return {}

    # Annualization factor for daily returns
    ann_factor = np.sqrt(252)

    mean_ret = np.mean(returns)
    std_ret = np.std(returns) + 1e-10
    downside = returns[returns < 0]
    downside_std = np.std(downside) + 1e-10 if len(downside) > 0 else 1e-10

    sharpe = (mean_ret / std_ret) * ann_factor
    sortino = (mean_ret / downside_std) * ann_factor

    # Max drawdown
    cumulative = pv / pv[0]
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()

    # Total return and CAGR
    total_return = (pv[-1] - pv[0]) / pv[0]
    n_years = len(returns) / 252
    cagr = (1 + total_return) ** (1 / max(n_years, 0.001)) - 1 if total_return > -1 else -1.0

    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0.0

    # Win rate
    win_rate = np.mean(returns > 0)

    return {
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown": round(max_drawdown * 100, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "calmar_ratio": round(calmar, 3),
        "win_rate_pct": round(win_rate * 100, 2),
        "avg_daily_return_pct": round(mean_ret * 100, 4),
        "daily_vol_pct": round(std_ret * 100, 4),
    }


def classify_strategy(action_log: list) -> dict:
    """
    Classify what strategy an agent learned by analyzing its trade pattern.

    This is the KEY multi-agent research finding: identical architectures,
    trained together in competition, learned qualitatively different strategies.

    Strategy signals:
    - Momentum: positive correlation between recent price trend and BUY actions
    - Mean-reversion: negative correlation (buy dips, sell rallies)
    - Market-making: high trade frequency, balanced buy/sell
    - Passive/HODL: low trade count, mostly HOLD
    """
    if not action_log:
        return {"strategy": "unknown", "trade_frequency": 0}

    actions = np.array([d["action"] for d in action_log])
    prices = np.array([d["price"] for d in action_log])

    n_buy = np.sum(actions == 1)
    n_sell = np.sum(actions == 2)
    n_hold = np.sum(actions == 0)
    total = len(actions)
    trade_frequency = (n_buy + n_sell) / total

    # Price momentum over 5-step window at each BUY/SELL point
    buy_price_momentum = []
    sell_price_momentum = []
    window = 5

    for i in range(window, len(actions)):
        recent_return = (prices[i] - prices[i - window]) / prices[i - window]
        if actions[i] == 1:  # BUY
            buy_price_momentum.append(recent_return)
        elif actions[i] == 2:  # SELL
            sell_price_momentum.append(recent_return)

    avg_buy_momentum = np.mean(buy_price_momentum) if buy_price_momentum else 0.0
    avg_sell_momentum = np.mean(sell_price_momentum) if sell_price_momentum else 0.0

    # Classify:
    # Momentum: buys on up-moves, sells on down-moves → avg_buy_momentum > 0
    # Mean-rev: buys on down-moves, sells on up-moves → avg_buy_momentum < 0
    # Market-maker: trades frequently, ~50% buy / 50% sell

    buy_sell_balance = n_buy / (n_buy + n_sell + 1)  # 0=all sell, 1=all buy, 0.5=balanced

    if trade_frequency > 0.4 and 0.35 < buy_sell_balance < 0.65:
        strategy = "market_making"
    elif avg_buy_momentum > 0.002 and n_buy > n_sell:
        strategy = "momentum"
    elif avg_buy_momentum < -0.002 or avg_sell_momentum > 0.002:
        strategy = "mean_reversion"
    elif trade_frequency < 0.05:
        strategy = "passive_hold"
    else:
        strategy = "mixed"

    return {
        "strategy": strategy,
        "trade_frequency": round(trade_frequency, 3),
        "buy_sell_balance": round(buy_sell_balance, 3),
        "avg_buy_momentum": round(avg_buy_momentum, 5),
        "avg_sell_momentum": round(avg_sell_momentum, 5),
        "n_buy": int(n_buy),
        "n_sell": int(n_sell),
        "n_hold": int(n_hold),
    }


def buy_and_hold_benchmark(test_prices: pd.Series, initial_cash: float = 10000.0):
    """Simple buy-and-hold baseline to compare against."""
    prices = test_prices.values
    shares = initial_cash / prices[0]
    portfolio = [shares * p for p in prices]
    return portfolio


def run_full_evaluation(checkpoint_dir: str, num_agents: int = 3):
    """Complete evaluation pipeline — call this after training."""
    import pickle

    env_probe = MultiAgentTradingEnv(num_agents=num_agents, split="test")
    obs_dim = env_probe.observation_space("agent_0").shape[0]
    test_prices = pd.Series(env_probe.prices)
    env_probe.close()

    # Load agents
    agents_policies = load_agents(checkpoint_dir, num_agents, obs_dim)

    # Run backtest
    print("\nRunning backtest on test set...")
    portfolio_histories, action_logs = run_backtest(agents_policies, num_agents)

    # Compute metrics
    results = {}
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS (Test Set: 2023-2024)")
    print("=" * 60)

    for agent_name in [f"agent_{i}" for i in range(num_agents)]:
        pv_hist = portfolio_histories[agent_name]
        metrics = compute_financial_metrics(pv_hist)
        strategy_info = classify_strategy(action_logs[agent_name])

        results[agent_name] = {
            "portfolio_history": pv_hist,
            "action_log": action_logs[agent_name],
            "metrics": metrics,
            "strategy": strategy_info,
        }

        print(f"\n{agent_name.upper()} — Strategy: {strategy_info['strategy'].upper()}")
        print(f"  Portfolio: ${pv_hist[-1]:.0f} (started ${INITIAL_CASH:.0f})")
        print(f"  Total Return: {metrics.get('total_return_pct', 0):+.1f}%")
        print(f"  Sharpe: {metrics.get('sharpe_ratio', 0):.2f} | Sortino: {metrics.get('sortino_ratio', 0):.2f}")
        print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.1f}%")
        print(f"  CAGR: {metrics.get('cagr_pct', 0):.1f}%")
        print(f"  Trades: {strategy_info['n_buy']} buys, {strategy_info['n_sell']} sells, {strategy_info['n_hold']} holds")
        print(f"  Trade Frequency: {strategy_info['trade_frequency']:.1%}")

    # Buy-and-hold benchmark
    bah = buy_and_hold_benchmark(test_prices)
    bah_metrics = compute_financial_metrics(bah)
    results["buy_and_hold"] = {
        "portfolio_history": bah,
        "metrics": bah_metrics,
    }
    print(f"\nBUY & HOLD BENCHMARK")
    print(f"  Total Return: {bah_metrics.get('total_return_pct', 0):+.1f}%")
    print(f"  Sharpe: {bah_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  Max Drawdown: {bah_metrics.get('max_drawdown', 0):.1f}%")

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "backtest_results.pkl"), "wb") as f:
        pickle.dump(results, f)
    print(f"\nResults saved to {RESULTS_DIR}/backtest_results.pkl")

    return results


if __name__ == "__main__":
    ckpt_dir = os.path.join(os.path.dirname(__file__), "..", "results", "checkpoints")
    results = run_full_evaluation(ckpt_dir, num_agents=3)
