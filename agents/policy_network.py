"""
Actor-Critic Policy Network for each trading agent.

Architecture choice — why this design:
- Shared trunk: 3 fully-connected layers extract common features from the
  observation (market data + portfolio state). Shared representation is cheaper
  and converges faster than separate networks for actor and critic.
- Actor head: outputs logits over 3 discrete actions (Hold/Buy/Sell).
  PPO samples from this distribution and optimizes the policy.
- Critic head: outputs a single scalar V(s) — the expected future return from
  this state. PPO uses this to compute Advantage = R - V(s) for policy updates.
- Layer Norm (not Batch Norm): financial time series are non-stationary; Layer
  Norm works per-sample so it doesn't conflate statistics across the batch.
- Orthogonal init with gain=sqrt(2) for hidden layers — standard PPO practice,
  prevents vanishing/exploding gradients at initialization.
"""

import torch
import torch.nn as nn
import numpy as np


def layer_init(layer, std=np.sqrt(2), bias_const=0.0):
    """Orthogonal initialization — empirically better for PPO than Xavier."""
    nn.init.orthogonal_(layer.weight, std)
    nn.init.constant_(layer.bias, bias_const)
    return layer


class TradingActorCritic(nn.Module):
    """
    Single network with shared trunk, separate actor and critic heads.
    Used by PPO: actor provides action distribution, critic provides value estimate.
    """

    def __init__(self, obs_dim: int, action_dim: int = 3, hidden_dim: int = 256):
        super().__init__()

        # Shared feature extractor
        self.trunk = nn.Sequential(
            layer_init(nn.Linear(obs_dim, hidden_dim)),
            nn.LayerNorm(hidden_dim),
            nn.Tanh(),
            layer_init(nn.Linear(hidden_dim, hidden_dim)),
            nn.LayerNorm(hidden_dim),
            nn.Tanh(),
            layer_init(nn.Linear(hidden_dim, hidden_dim // 2)),
            nn.LayerNorm(hidden_dim // 2),
            nn.Tanh(),
        )

        # Actor: policy logits (low std init so initial policy is near-uniform)
        self.actor_head = layer_init(
            nn.Linear(hidden_dim // 2, action_dim), std=0.01
        )

        # Critic: state value (std=1 is standard for value head)
        self.critic_head = layer_init(
            nn.Linear(hidden_dim // 2, 1), std=1.0
        )

    def get_value(self, x: torch.Tensor) -> torch.Tensor:
        """Critic forward pass — used during PPO value loss computation."""
        return self.critic_head(self.trunk(x))

    def get_action_and_value(self, x: torch.Tensor, action=None):
        """
        Actor-critic forward pass.

        During rollout collection: action=None, sample from distribution.
        During PPO update: action=stored_action, evaluate log_prob of that action.

        Returns:
            action: sampled or provided action
            log_prob: log probability of the action (for importance ratio)
            entropy: policy entropy (added to loss to encourage exploration)
            value: critic estimate V(s)
        """
        features = self.trunk(x)
        logits = self.actor_head(features)
        value = self.critic_head(features)

        dist = torch.distributions.Categorical(logits=logits)
        if action is None:
            action = dist.sample()

        return action, dist.log_prob(action), dist.entropy(), value
