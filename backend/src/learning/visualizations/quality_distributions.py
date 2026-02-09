"""
Quality score distribution plots for academic papers.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def plot_quality_distribution(
    scores: list[float],
    output_path: str,
    title: str = "Quality Score Distribution",
    bins: int = 20,
) -> str:
    """Plot histogram + box plot of quality scores."""
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={"height_ratios": [3, 1]})

    # Histogram
    ax1.hist(scores, bins=bins, edgecolor="black", alpha=0.7, color="steelblue")
    ax1.axvline(np.mean(scores), color="red", linestyle="--", label=f"Mean: {np.mean(scores):.1f}")
    ax1.axvline(np.median(scores), color="green", linestyle="--", label=f"Median: {np.median(scores):.1f}")
    ax1.set_xlabel("Quality Score")
    ax1.set_ylabel("Count")
    ax1.set_title(title)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Box plot
    ax2.boxplot(scores, vert=False, widths=0.6)
    ax2.set_xlabel("Quality Score")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_reward_components(
    component_history: list[dict[str, float]],
    output_path: str,
    title: str = "Reward Component Evolution",
) -> str:
    """Plot each reward component over trials."""
    import matplotlib.pyplot as plt

    if not component_history:
        return output_path

    components = list(component_history[0].keys())
    trials = list(range(1, len(component_history) + 1))

    fig, ax = plt.subplots(1, 1, figsize=(12, 6))

    for comp in components:
        values = [h.get(comp, 0) for h in component_history]
        ax.plot(trials, values, "-o", label=comp, markersize=3, alpha=0.8)

    ax.set_xlabel("Trial Number")
    ax.set_ylabel("Component Value")
    ax.set_title(title)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_ablation_results(
    results: list[dict],
    output_path: str,
    title: str = "Ablation Study Results",
) -> str:
    """Plot ablation study as bar chart."""
    import matplotlib.pyplot as plt

    components = [r["component_removed"] for r in results]
    deltas = [r["delta"] for r in results]
    colors = ["red" if d > 0 else "blue" for d in deltas]

    fig, ax = plt.subplots(1, 1, figsize=(10, 6))

    bars = ax.barh(components, deltas, color=colors, alpha=0.7, edgecolor="black")
    ax.set_xlabel("Δ Reward (Baseline - Ablated)")
    ax.set_title(title)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(True, alpha=0.3, axis="x")

    for bar, delta in zip(bars, deltas):
        ax.text(
            bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
            f"{delta:+.4f}", va="center", fontsize=9,
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path
