"""
Multi-Agent Trading Environment built on PettingZoo's AEC (Agent-Environment Cycle) API.

Design decisions:
- Each agent independently manages its own portfolio (cash + position)
- Agents observe market features PLUS other agents' positions — this is what
  makes strategies emergent: agents can learn to front-run or counter competitors
- Actions are discrete: 0=Hold, 1=Buy, 2=Sell (simplifies exploration vs continuous)
- Reward = realized + unrealized P&L delta per step (shapes toward profit, not just
  holding a winning position forever)
- Transaction costs modeled as 0.1% per trade to penalize excessive churning
"""

import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
import pickle
import os

from pettingzoo import AECEnv
from pettingzoo.utils import wrappers
from pettingzoo.utils.agent_selector import agent_selector


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# Action constants
HOLD = 0
BUY = 1
SELL = 2

TRANSACTION_COST = 0.001  # 0.1% per trade
INITIAL_CASH = 10_000.0
SHARES_PER_TRADE = 10       # fixed lot size keeps action space simple
MAX_SHARES = 100            # position limit per agent


def load_data(split="train"):
    path = os.path.join(DATA_DIR, f"{split}.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


FEATURE_COLS = [
    "rsi", "macd", "macd_signal", "macd_diff",
    "bb_width", "bb_pct", "atr", "sma_cross",
    "returns", "log_returns", "volatility_20", "volume_ratio",
]


def env(num_agents=3, split="train", episode_length=252):
    """Factory function — PettingZoo convention."""
    raw_env = MultiAgentTradingEnv(num_agents=num_agents, split=split, episode_length=episode_length)
    # Wrappers: order enforcing ensures agents act in turn
    raw_env = wrappers.OrderEnforcingWrapper(raw_env)
    return raw_env


class MultiAgentTradingEnv(AECEnv):
    """
    AEC (Agent-Environment Cycle) environment.

    Each step, one agent acts; the environment updates; the next agent's
    observation is computed. All agents share the same market price stream
    but maintain separate portfolios.

    Observation per agent (normalized):
        [12 market features] + [own_position, own_cash_pct] + [other agents' positions]
        Total dim = 12 + 2 + (num_agents - 1)
    """

    metadata = {"render_modes": ["human"], "name": "multi_agent_trading_v0"}

    def __init__(self, num_agents=3, split="train", episode_length=252):
        super().__init__()

        self.num_agents_count = num_agents
        self.episode_length = episode_length
        self.split = split

        # Load market data
        self.data = load_data(split)
        self.prices = self.data["Close"].values.astype(np.float32)
        self.features = self.data[FEATURE_COLS].values.astype(np.float32)

        # Normalize features to zero mean / unit std (computed on training data)
        self._feat_mean = self.features.mean(axis=0)
        self._feat_std = self.features.std(axis=0) + 1e-8
        self.norm_features = (self.features - self._feat_mean) / self._feat_std

        # PettingZoo agent list
        self.possible_agents = [f"agent_{i}" for i in range(num_agents)]
        self.agents = self.possible_agents[:]

        # Observation: market features + own state + other agents' positions
        obs_dim = len(FEATURE_COLS) + 2 + (num_agents - 1)
        self._obs_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )
        self._act_space = spaces.Discrete(3)  # HOLD, BUY, SELL

        # Internal state
        self._reset_state()

    # ------------------------------------------------------------------ spaces

    def observation_space(self, agent):
        return self._obs_space

    def action_space(self, agent):
        return self._act_space

    # ------------------------------------------------------------------ reset

    def reset(self, seed=None, options=None):
        if seed is not None:
            np.random.seed(seed)

        self._reset_state()

        # PettingZoo bookkeeping
        self.agents = self.possible_agents[:]
        self._agent_selector = agent_selector(self.agents)
        self.agent_selection = self._agent_selector.next()

        self.rewards = {a: 0.0 for a in self.agents}
        self._cumulative_rewards = {a: 0.0 for a in self.agents}
        self.terminations = {a: False for a in self.agents}
        self.truncations = {a: False for a in self.agents}
        self.infos = {a: {} for a in self.agents}

        observations = {a: self._get_obs(a) for a in self.agents}
        return observations, self.infos

    def _reset_state(self):
        # Pick a random start so each episode sees different market conditions
        max_start = len(self.prices) - self.episode_length - 1
        self.start_idx = np.random.randint(0, max(1, max_start))
        self.current_step = 0

        # Per-agent portfolio state
        self.cash = {a: INITIAL_CASH for a in self.possible_agents}
        self.shares = {a: 0 for a in self.possible_agents}
        self.prev_portfolio_value = {a: INITIAL_CASH for a in self.possible_agents}
        self.trade_count = {a: 0 for a in self.possible_agents}
        self.portfolio_history = {a: [INITIAL_CASH] for a in self.possible_agents}

    # ------------------------------------------------------------------ step

    def step(self, action):
        agent = self.agent_selection

        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)
            return

        price = self._current_price()

        # Execute trade
        reward = self._execute_action(agent, action, price)
        self.rewards[agent] = reward
        self._cumulative_rewards[agent] += reward

        # Store portfolio value for history
        pv = self._portfolio_value(agent, price)
        self.portfolio_history[agent].append(pv)
        self.prev_portfolio_value[agent] = pv

        # Advance step after last agent in the cycle acts
        if self._agent_selector.is_last():
            self.current_step += 1
            done = self.current_step >= self.episode_length

            for a in self.agents:
                self.terminations[a] = done
                self.truncations[a] = False
                self.infos[a] = {
                    "portfolio_value": self._portfolio_value(a, self._current_price()),
                    "shares": self.shares[a],
                    "cash": self.cash[a],
                    "trade_count": self.trade_count[a],
                }

        self.agent_selection = self._agent_selector.next()

    def _execute_action(self, agent, action, price):
        prev_value = self._portfolio_value(agent, price)

        if action == BUY:
            cost = price * SHARES_PER_TRADE * (1 + TRANSACTION_COST)
            if self.cash[agent] >= cost and self.shares[agent] + SHARES_PER_TRADE <= MAX_SHARES:
                self.cash[agent] -= cost
                self.shares[agent] += SHARES_PER_TRADE
                self.trade_count[agent] += 1

        elif action == SELL:
            if self.shares[agent] >= SHARES_PER_TRADE:
                proceeds = price * SHARES_PER_TRADE * (1 - TRANSACTION_COST)
                self.cash[agent] += proceeds
                self.shares[agent] -= SHARES_PER_TRADE
                self.trade_count[agent] += 1

        new_value = self._portfolio_value(agent, price)
        # Reward = percent change in portfolio value, scaled
        reward = (new_value - prev_value) / INITIAL_CASH * 100
        return float(reward)

    # ------------------------------------------------------------------ helpers

    def _current_price(self):
        idx = min(self.start_idx + self.current_step, len(self.prices) - 1)
        return float(self.prices[idx])

    def _portfolio_value(self, agent, price):
        return self.cash[agent] + self.shares[agent] * price

    def _get_obs(self, agent):
        idx = min(self.start_idx + self.current_step, len(self.norm_features) - 1)
        market_feats = self.norm_features[idx].copy()

        price = self._current_price()
        total_value = self._portfolio_value(agent, price)

        # Own state: position as fraction of max shares, cash as fraction of initial
        own_position = self.shares[agent] / MAX_SHARES
        own_cash_pct = self.cash[agent] / INITIAL_CASH

        # Other agents' positions (normalized) — key multi-agent signal
        other_positions = []
        for other in self.possible_agents:
            if other != agent:
                other_positions.append(self.shares[other] / MAX_SHARES)

        obs = np.concatenate([
            market_feats,
            [own_position, own_cash_pct],
            other_positions,
        ]).astype(np.float32)

        return obs

    def observe(self, agent):
        return self._get_obs(agent)

    def render(self):
        price = self._current_price()
        print(f"\nStep {self.current_step} | Price: ${price:.2f}")
        for a in self.possible_agents:
            pv = self._portfolio_value(a, price)
            print(f"  {a}: ${pv:.0f} | shares={self.shares[a]} | cash=${self.cash[a]:.0f}")

    def close(self):
        pass
