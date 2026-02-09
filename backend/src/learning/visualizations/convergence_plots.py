"""
Convergence plots for RL optimization experiments.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def plot_reward_convergence(
    rewards: list[float],
    output_path: str,
    title: str = "Reward Convergence",
) -> str:
    """Plot reward convergence curve with running best."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))

    trials = list(range(1, len(rewards) + 1))
    running_best = np.maximum.accumulate(rewards)

    ax.plot(trials, rewards, "o-", alpha=0.5, label="Trial Reward", markersize=4)
    ax.plot(trials, running_best, "r-", linewidth=2, label="Running Best")
    ax.fill_between(trials, 0, running_best, alpha=0.1, color="red")

    ax.set_xlabel("Trial Number")
    ax.set_ylabel("Reward")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Convergence plot saved: %s", output_path)
    return output_path


def plot_cumulative_regret(
    rewards: list[float],
    oracle_reward: float,
    output_path: str,
    title: str = "Cumulative Regret",
) -> str:
    """Plot cumulative regret vs oracle."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))

    regret = np.cumsum([oracle_reward - r for r in rewards])

    ax.plot(range(1, len(regret) + 1), regret, "b-", linewidth=2)
    ax.set_xlabel("Trial Number")
    ax.set_ylabel("Cumulative Regret")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_exploration_exploitation(
    uncertainties: list[float],
    rewards: list[float],
    output_path: str,
) -> str:
    """Plot GP uncertainty reduction alongside reward improvement."""
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    trials = list(range(1, len(rewards) + 1))
    ax1.plot(trials, rewards, "o-", alpha=0.6, label="Reward")
    ax1.set_ylabel("Reward")
    ax1.set_title("Exploration vs Exploitation")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    unc_trials = list(range(1, len(uncertainties) + 1))
    ax2.plot(unc_trials, uncertainties, "g-", linewidth=2, label="Mean GP Uncertainty (σ)")
    ax2.set_xlabel("Trial Number")
    ax2.set_ylabel("Uncertainty")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path
