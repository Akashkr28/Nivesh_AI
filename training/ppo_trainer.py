"""
Proximal Policy Optimization (PPO) trainer for multi-agent trading.

Why PPO over other RL algorithms:
- DQN (off-policy, discrete) works but can be unstable with financial rewards
- A3C (on-policy, async) scales poorly on a single machine
- PPO: on-policy, stable via clipped surrogate objective, works well with
  discrete actions, proven in financial RL literature

Independent Learners setup:
- Each agent has its own PPO trainer and replay buffer
- They share the environment but NOT weights or gradients
- This is intentional: we want agents to diverge into different strategies
- More complex: MADDPG (shared critic) — left as extension

PPO Core Mechanics:
1. Collect T timesteps of experience per agent (rollout phase)
2. Compute advantages using GAE (Generalized Advantage Estimation)
3. Run K epochs of minibatch updates with clipped objective
4. Clipping prevents policy from changing too drastically in one update
   — the "proximal" part of PPO

Hyperparameter rationale:
- clip_eps=0.2: standard; smaller is more conservative
- gamma=0.99: long time horizon, discount future rewards slowly
- gae_lambda=0.95: GAE trades bias vs variance; 0.95 is standard
- ent_coef=0.01: small entropy bonus keeps policy from collapsing too early
- vf_coef=0.5: value loss is typically larger, so halved to balance
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os
import json
import pickle
from collections import defaultdict

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.policy_network import TradingActorCritic
from envs.trading_env import MultiAgentTradingEnv

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {DEVICE}")


# ── Rollout Buffer ─────────────────────────────────────────────────────────────

class RolloutBuffer:
    """
    Stores one rollout (T timesteps) for one agent.
    PPO is on-policy: buffer is cleared after every update.
    """

    def __init__(self, rollout_steps: int, obs_dim: int):
        self.rollout_steps = rollout_steps
        self.obs = np.zeros((rollout_steps, obs_dim), dtype=np.float32)
        self.actions = np.zeros(rollout_steps, dtype=np.int64)
        self.log_probs = np.zeros(rollout_steps, dtype=np.float32)
        self.rewards = np.zeros(rollout_steps, dtype=np.float32)
        self.values = np.zeros(rollout_steps, dtype=np.float32)
        self.dones = np.zeros(rollout_steps, dtype=np.float32)
        self.ptr = 0

    def add(self, obs, action, log_prob, reward, value, done):
        if self.ptr >= self.rollout_steps:
            return
        self.obs[self.ptr] = obs
        self.actions[self.ptr] = action
        self.log_probs[self.ptr] = log_prob
        self.rewards[self.ptr] = reward
        self.values[self.ptr] = value
        self.dones[self.ptr] = done
        self.ptr += 1

    def full(self):
        return self.ptr >= self.rollout_steps

    def reset(self):
        self.ptr = 0

    def compute_gae(self, last_value: float, gamma: float, gae_lambda: float):
        """
        Generalized Advantage Estimation (GAE).

        Advantage A(s,a) = Q(s,a) - V(s) tells us: was this action better
        than average? GAE smooths this estimate using a weighted sum of
        n-step TD errors, controlled by lambda:
        - lambda=0: pure TD(0), low variance, high bias
        - lambda=1: Monte Carlo, low bias, high variance
        - lambda=0.95: standard sweet spot
        """
        T = self.ptr
        advantages = np.zeros(T, dtype=np.float32)
        gae = 0.0

        for t in reversed(range(T)):
            next_value = last_value if t == T - 1 else self.values[t + 1]
            next_non_terminal = 1.0 - (self.dones[t] if t == T - 1 else 0.0)
            delta = self.rewards[t] + gamma * next_value * next_non_terminal - self.values[t]
            gae = delta + gamma * gae_lambda * next_non_terminal * gae
            advantages[t] = gae

        returns = advantages + self.values[:T]
        return advantages, returns


# ── Per-Agent PPO ──────────────────────────────────────────────────────────────

class PPOAgent:
    """One PPO agent — independent of other agents."""

    def __init__(
        self,
        agent_id: str,
        obs_dim: int,
        action_dim: int = 3,
        lr: float = 3e-4,
        rollout_steps: int = 512,
        n_epochs: int = 10,
        minibatch_size: int = 64,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_eps: float = 0.2,
        ent_coef: float = 0.01,
        vf_coef: float = 0.5,
        max_grad_norm: float = 0.5,
    ):
        self.agent_id = agent_id
        self.obs_dim = obs_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_eps = clip_eps
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef
        self.max_grad_norm = max_grad_norm
        self.n_epochs = n_epochs
        self.minibatch_size = minibatch_size
        self.rollout_steps = rollout_steps

        self.policy = TradingActorCritic(obs_dim, action_dim).to(DEVICE)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=lr, eps=1e-5)
        self.buffer = RolloutBuffer(rollout_steps, obs_dim)

        # Tracking
        self.update_count = 0
        self.episode_rewards = []
        self.train_metrics = defaultdict(list)

    @torch.no_grad()
    def act(self, obs: np.ndarray):
        """Sample action during rollout collection."""
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(DEVICE)
        action, log_prob, _, value = self.policy.get_action_and_value(obs_t)
        return (
            action.item(),
            log_prob.item(),
            value.squeeze().item(),
        )

    def store(self, obs, action, log_prob, reward, value, done):
        self.buffer.add(obs, action, log_prob, reward, value, done)

    def update(self, last_obs: np.ndarray):
        """
        PPO update — runs after rollout_steps of experience collected.

        Steps:
        1. Compute GAE advantages from stored rewards + values
        2. Normalize advantages (reduces variance, stabilizes training)
        3. For n_epochs: shuffle data, split into minibatches, compute loss
        4. Loss = policy_loss + vf_coef * value_loss - ent_coef * entropy

        The clipped surrogate loss:
            ratio = new_prob / old_prob
            L = min(ratio * A, clip(ratio, 1-eps, 1+eps) * A)
        This prevents the policy from moving too far from the behavior policy.
        """
        if self.buffer.ptr == 0:
            return {}

        # Bootstrap value for last state
        with torch.no_grad():
            last_obs_t = torch.FloatTensor(last_obs).unsqueeze(0).to(DEVICE)
            last_value = self.policy.get_value(last_obs_t).squeeze().item()

        advantages, returns = self.buffer.compute_gae(last_value, self.gamma, self.gae_lambda)

        T = self.buffer.ptr
        obs_t = torch.FloatTensor(self.buffer.obs[:T]).to(DEVICE)
        actions_t = torch.LongTensor(self.buffer.actions[:T]).to(DEVICE)
        old_log_probs_t = torch.FloatTensor(self.buffer.log_probs[:T]).to(DEVICE)
        advantages_t = torch.FloatTensor(advantages).to(DEVICE)
        returns_t = torch.FloatTensor(returns).to(DEVICE)

        # Normalize advantages
        advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

        metrics = defaultdict(list)

        for _ in range(self.n_epochs):
            indices = np.random.permutation(T)
            for start in range(0, T, self.minibatch_size):
                mb_idx = indices[start: start + self.minibatch_size]

                _, new_log_probs, entropy, values = self.policy.get_action_and_value(
                    obs_t[mb_idx], actions_t[mb_idx]
                )

                # Policy loss (clipped surrogate)
                ratio = torch.exp(new_log_probs - old_log_probs_t[mb_idx])
                pg_loss1 = -advantages_t[mb_idx] * ratio
                pg_loss2 = -advantages_t[mb_idx] * torch.clamp(ratio, 1 - self.clip_eps, 1 + self.clip_eps)
                policy_loss = torch.max(pg_loss1, pg_loss2).mean()

                # Value loss (clipped to match PPO-style value clipping)
                value_loss = nn.functional.mse_loss(values.squeeze(), returns_t[mb_idx])

                # Entropy bonus (encourages exploration)
                entropy_loss = -entropy.mean()

                loss = policy_loss + self.vf_coef * value_loss + self.ent_coef * entropy_loss

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.optimizer.step()

                metrics["policy_loss"].append(policy_loss.item())
                metrics["value_loss"].append(value_loss.item())
                metrics["entropy"].append(-entropy_loss.item())
                metrics["approx_kl"].append(((ratio - 1) - (ratio.log())).mean().item())

        self.buffer.reset()
        self.update_count += 1

        avg_metrics = {k: np.mean(v) for k, v in metrics.items()}
        for k, v in avg_metrics.items():
            self.train_metrics[k].append(v)

        return avg_metrics

    def save(self, path: str):
        torch.save({
            "policy_state": self.policy.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "update_count": self.update_count,
            "train_metrics": dict(self.train_metrics),
        }, path)

    def load(self, path: str):
        ckpt = torch.load(path, map_location=DEVICE)
        self.policy.load_state_dict(ckpt["policy_state"])
        self.optimizer.load_state_dict(ckpt["optimizer_state"])
        self.update_count = ckpt["update_count"]
        self.train_metrics = defaultdict(list, ckpt["train_metrics"])


# ── Multi-Agent Training Loop ──────────────────────────────────────────────────

def train(
    num_agents: int = 3,
    total_timesteps: int = 500_000,
    rollout_steps: int = 512,
    episode_length: int = 252,
    save_dir: str = None,
    wandb_enabled: bool = False,
):
    if save_dir is None:
        save_dir = os.path.join(os.path.dirname(__file__), "..", "results", "checkpoints")
    os.makedirs(save_dir, exist_ok=True)

    # Initialize environment and agents
    raw_env = MultiAgentTradingEnv(
        num_agents=num_agents, split="train", episode_length=episode_length
    )

    obs_dim = raw_env.observation_space("agent_0").shape[0]
    print(f"Observation dim: {obs_dim} | Action dim: 3 | Agents: {num_agents}")

    agents = {
        f"agent_{i}": PPOAgent(
            agent_id=f"agent_{i}",
            obs_dim=obs_dim,
            rollout_steps=rollout_steps,
        )
        for i in range(num_agents)
    }

    if wandb_enabled:
        try:
            import wandb
            wandb.init(project="marl-trading", config={
                "num_agents": num_agents,
                "total_timesteps": total_timesteps,
                "rollout_steps": rollout_steps,
                "episode_length": episode_length,
            })
        except Exception as e:
            print(f"W&B init failed: {e}. Continuing without W&B.")
            wandb_enabled = False

    # Training state
    global_step = 0
    episode_num = 0
    episode_rewards = defaultdict(list)
    all_episode_data = []

    # Current observations
    observations, _ = raw_env.reset()
    last_obs = {a: observations.get(a, np.zeros(obs_dim)) for a in raw_env.possible_agents}

    print(f"\nStarting training: {total_timesteps} timesteps")
    print("=" * 60)

    while global_step < total_timesteps:
        # --- Rollout collection phase ---
        step_rewards = defaultdict(float)

        for _ in range(rollout_steps):
            # AEC: one agent acts per step
            agent_name = raw_env.agent_selection

            if agent_name not in agents:
                raw_env.step(raw_env.action_space(agent_name).sample())
                continue

            obs = last_obs[agent_name]
            action, log_prob, value = agents[agent_name].act(obs)

            raw_env.step(action)
            global_step += 1

            # Collect result
            reward = raw_env.rewards.get(agent_name, 0.0)
            done = raw_env.terminations.get(agent_name, False) or raw_env.truncations.get(agent_name, False)

            # Get next obs
            next_obs = raw_env.observe(agent_name)
            if next_obs is None:
                next_obs = np.zeros(obs_dim, dtype=np.float32)

            agents[agent_name].store(obs, action, log_prob, reward, value, done)
            last_obs[agent_name] = next_obs
            step_rewards[agent_name] += reward

            if done or len(raw_env.agents) == 0:
                # Episode ended — reset
                episode_num += 1
                for a in raw_env.possible_agents:
                    pv = raw_env.infos.get(a, {}).get("portfolio_value", 10000.0)
                    episode_rewards[a].append(pv)

                ep_data = {
                    "episode": episode_num,
                    "step": global_step,
                }
                for a in raw_env.possible_agents:
                    ep_data[f"{a}_portfolio_value"] = raw_env.infos.get(a, {}).get("portfolio_value", 10000.0)
                    ep_data[f"{a}_trade_count"] = raw_env.infos.get(a, {}).get("trade_count", 0)
                all_episode_data.append(ep_data)

                observations, _ = raw_env.reset()
                last_obs = {a: observations.get(a, np.zeros(obs_dim)) for a in raw_env.possible_agents}
                break

        # --- PPO update phase (after collecting rollout_steps) ---
        all_metrics = {}
        for agent_name, ppo_agent in agents.items():
            if ppo_agent.buffer.ptr > 0:
                metrics = ppo_agent.update(last_obs[agent_name])
                all_metrics[agent_name] = metrics

        # --- Logging ---
        if episode_num % 10 == 0 and episode_num > 0:
            print(f"\nEpisode {episode_num} | Steps: {global_step:,}")
            for a in agents:
                recent_pvs = episode_rewards[a][-10:]
                if recent_pvs:
                    avg_pv = np.mean(recent_pvs)
                    ret_pct = (avg_pv - 10000) / 10000 * 100
                    print(f"  {a}: avg portfolio=${avg_pv:.0f} ({ret_pct:+.1f}%)")
                if a in all_metrics and all_metrics[a]:
                    m = all_metrics[a]
                    print(f"       policy_loss={m.get('policy_loss', 0):.4f} | "
                          f"value_loss={m.get('value_loss', 0):.4f} | "
                          f"entropy={m.get('entropy', 0):.4f}")

            if wandb_enabled:
                log_data = {"global_step": global_step, "episode": episode_num}
                for a in agents:
                    recent_pvs = episode_rewards[a][-10:]
                    if recent_pvs:
                        log_data[f"{a}/portfolio_value"] = np.mean(recent_pvs)
                    if a in all_metrics and all_metrics[a]:
                        for k, v in all_metrics[a].items():
                            log_data[f"{a}/{k}"] = v
                wandb.log(log_data)

        # --- Save checkpoints ---
        if global_step % 50_000 == 0 and global_step > 0:
            for agent_name, ppo_agent in agents.items():
                ckpt_path = os.path.join(save_dir, f"{agent_name}_step{global_step}.pt")
                ppo_agent.save(ckpt_path)
            print(f"  Checkpoint saved at step {global_step}")

    # Final save
    for agent_name, ppo_agent in agents.items():
        final_path = os.path.join(save_dir, f"{agent_name}_final.pt")
        ppo_agent.save(final_path)
        print(f"Saved final model: {final_path}")

    # Save episode history
    history_path = os.path.join(save_dir, "..", "episode_history.pkl")
    with open(history_path, "wb") as f:
        pickle.dump(all_episode_data, f)

    print(f"\nTraining complete. {episode_num} episodes, {global_step} steps.")
    raw_env.close()
    return agents, all_episode_data


if __name__ == "__main__":
    agents, history = train(
        num_agents=3,
        total_timesteps=200_000,
        rollout_steps=512,
        episode_length=252,
    )
