"""
GP posterior distribution heatmaps for parameter sensitivity analysis.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def plot_parameter_heatmap(
    optimizer,
    param_x: str,
    param_y: str,
    output_path: str,
    resolution: int = 50,
    title: Optional[str] = None,
) -> str:
    """Plot 2D heatmap of GP posterior mean for a parameter pair."""
    import matplotlib.pyplot as plt

    space = optimizer.space
    px = space.get_bound(param_x)
    py = space.get_bound(param_y)

    x_vals = np.linspace(px.low, px.high, resolution)
    y_vals = np.linspace(py.low, py.high, resolution)
    xx, yy = np.meshgrid(x_vals, y_vals)

    # Build grid with other params at midpoint
    lows, highs = space.to_array_bounds()
    mid = (lows + highs) / 2

    x_idx = space.names.index(param_x)
    y_idx = space.names.index(param_y)

    grid = np.tile(mid, (resolution * resolution, 1))
    grid[:, x_idx] = xx.ravel()
    grid[:, y_idx] = yy.ravel()

    # Predict
    if optimizer._gp is None:
        logger.warning("GP not fitted, skipping heatmap")
        return output_path

    mean, std = optimizer._gp.predict(
        (grid - optimizer._X_mean) / optimizer._X_std, return_std=True
    )
    mean = mean * optimizer._y_std + optimizer._y_mean

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Mean heatmap
    im1 = axes[0].pcolormesh(
        xx, yy, mean.reshape(resolution, resolution), cmap="viridis", shading="auto"
    )
    axes[0].set_xlabel(param_x)
    axes[0].set_ylabel(param_y)
    axes[0].set_title("GP Posterior Mean")
    plt.colorbar(im1, ax=axes[0])

    # Uncertainty heatmap
    std_reshaped = std.reshape(resolution, resolution)
    im2 = axes[1].pcolormesh(
        xx, yy, std_reshaped, cmap="magma", shading="auto"
    )
    axes[1].set_xlabel(param_x)
    axes[1].set_ylabel(param_y)
    axes[1].set_title("GP Posterior Uncertainty (σ)")
    plt.colorbar(im2, ax=axes[1])

    # Overlay observations
    for ax in axes:
        if optimizer._X:
            X = np.array(optimizer._X)
            ax.scatter(X[:, x_idx], X[:, y_idx], c="red", s=20, zorder=5, edgecolors="white")

    fig.suptitle(title or f"Parameter Sensitivity: {param_x} vs {param_y}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Parameter heatmap saved: %s", output_path)
    return output_path


def plot_all_parameter_pairs(
    optimizer,
    output_dir: str,
    top_n: int = 6,
) -> list[str]:
    """Generate heatmaps for top parameter pairs."""
    from itertools import combinations
    from pathlib import Path

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    names = optimizer.space.names
    pairs = list(combinations(names, 2))[:top_n]

    paths = []
    for px, py in pairs:
        path = str(Path(output_dir) / f"heatmap_{px}_vs_{py}.png")
        plot_parameter_heatmap(optimizer, px, py, path)
        paths.append(path)
    return paths
