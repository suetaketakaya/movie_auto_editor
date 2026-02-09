"""
LLM-Human evaluation correlation analysis.
Generates scatter plots and Spearman ρ for academic papers.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def plot_llm_human_correlation(
    llm_scores: list[float],
    human_scores: list[float],
    output_path: str,
    title: str = "LLM vs Human Evaluation Correlation",
) -> str:
    """Scatter plot with regression line and Spearman ρ."""
    import matplotlib.pyplot as plt
    from scipy import stats

    rho, p_value = stats.spearmanr(llm_scores, human_scores)

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))

    ax.scatter(llm_scores, human_scores, alpha=0.6, s=40, edgecolors="black", linewidth=0.5)

    # Regression line
    z = np.polyfit(llm_scores, human_scores, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(llm_scores), max(llm_scores), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label=f"Spearman ρ = {rho:.3f} (p = {p_value:.4f})")

    # Identity line
    lims = [
        min(min(llm_scores), min(human_scores)),
        max(max(llm_scores), max(human_scores)),
    ]
    ax.plot(lims, lims, "k--", alpha=0.3, label="Identity")

    ax.set_xlabel("LLM Quality Score")
    ax.set_ylabel("Human Quality Score")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Correlation plot saved: %s (ρ=%.3f)", output_path, rho)
    return output_path


def compute_correlation_metrics(
    llm_scores: list[float],
    human_scores: list[float],
) -> dict:
    """Compute various correlation metrics."""
    from scipy import stats

    spearman_rho, spearman_p = stats.spearmanr(llm_scores, human_scores)
    pearson_r, pearson_p = stats.pearsonr(llm_scores, human_scores)
    kendall_tau, kendall_p = stats.kendalltau(llm_scores, human_scores)

    mae = float(np.mean(np.abs(np.array(llm_scores) - np.array(human_scores))))
    rmse = float(np.sqrt(np.mean((np.array(llm_scores) - np.array(human_scores)) ** 2)))

    return {
        "spearman_rho": float(spearman_rho),
        "spearman_p": float(spearman_p),
        "pearson_r": float(pearson_r),
        "pearson_p": float(pearson_p),
        "kendall_tau": float(kendall_tau),
        "kendall_p": float(kendall_p),
        "mae": mae,
        "rmse": rmse,
        "n_samples": len(llm_scores),
    }
