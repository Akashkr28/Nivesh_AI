"""
Master runner — executes the full pipeline in order:
  1. Download & preprocess data
  2. Train all agents (PPO, multi-agent)
  3. Run backtest on test set
  4. Generate visualization dashboard

Usage:
  python run_all.py                   # full run (200k steps)
  python run_all.py --quick           # quick demo (50k steps)
  python run_all.py --eval-only       # skip training, run eval on existing checkpoints
  python run_all.py --viz-only        # just regenerate charts from saved results
"""

import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def step1_data():
    print("\n" + "=" * 60)
    print("STEP 1: Data Download & Feature Engineering")
    print("=" * 60)
    from data.download_data import download_and_process
    train, test = download_and_process()
    print(f"Train shape: {train.shape}, Test shape: {test.shape}")
    return train, test


def step2_train(total_timesteps: int = 200_000, num_agents: int = 3):
    print("\n" + "=" * 60)
    print("STEP 2: Multi-Agent PPO Training")
    print("=" * 60)
    from training.ppo_trainer import train
    agents, history = train(
        num_agents=num_agents,
        total_timesteps=total_timesteps,
        rollout_steps=512,
        episode_length=252,
        save_dir=os.path.join(BASE, "results", "checkpoints"),
        wandb_enabled=False,
    )
    return agents, history


def step3_evaluate(num_agents: int = 3):
    print("\n" + "=" * 60)
    print("STEP 3: Backtesting & Evaluation")
    print("=" * 60)
    from evaluation.backtest import run_full_evaluation
    ckpt_dir = os.path.join(BASE, "results", "checkpoints")
    results = run_full_evaluation(ckpt_dir, num_agents=num_agents)
    return results


def step4_visualize():
    print("\n" + "=" * 60)
    print("STEP 4: Generating Visualization Dashboard")
    print("=" * 60)
    from visualization.dashboard import generate_all_charts
    charts = generate_all_charts()
    print(f"\nDashboard ready. Open in browser:")
    dashboard_path = os.path.join(BASE, "results", "charts", "dashboard.html")
    print(f"  file://{dashboard_path}")
    return charts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run with 50k timesteps for quick demo")
    parser.add_argument("--eval-only", action="store_true", help="Skip training, run eval only")
    parser.add_argument("--viz-only", action="store_true", help="Only regenerate charts")
    parser.add_argument("--timesteps", type=int, default=200_000, help="Training timesteps")
    parser.add_argument("--agents", type=int, default=3, help="Number of competing agents")
    args = parser.parse_args()

    timesteps = 50_000 if args.quick else args.timesteps

    if args.viz_only:
        step4_visualize()
    elif args.eval_only:
        step3_evaluate(args.agents)
        step4_visualize()
    else:
        step1_data()
        step2_train(total_timesteps=timesteps, num_agents=args.agents)
        step3_evaluate(args.agents)
        step4_visualize()

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
