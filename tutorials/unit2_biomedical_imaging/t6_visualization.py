"""T6: Biomedical Image -- Visualization.
Course: 21CSE428T Healthcare Analytics, Unit 2.

Builds three visualizations for the same sample image used in T4/T5:
  1. Side-by-side original vs. processed (CLAHE-enhanced) panels
  2. A pixel-intensity histogram (raw vs. enhanced)
  3. The Otsu segmentation mask overlaid on the original as a colored
     contour boundary

This script recomputes CLAHE and the Otsu mask itself (via the same
skimage calls as T4) so it can run standalone -- it does not import T4,
keeping each tutorial script independently runnable per the assignment.

Usage: python t6_visualization.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from skimage import data, exposure, filters, measure

OUT = Path(__file__).parent / "outputs"


def side_by_side(original: np.ndarray, processed: np.ndarray) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    axes[0].imshow(original, cmap="gray")
    axes[0].set_title("Original (skimage.data.cell)")
    axes[0].axis("off")
    axes[1].imshow(processed, cmap="gray")
    axes[1].set_title("CLAHE-enhanced")
    axes[1].axis("off")
    path = OUT / "t6_side_by_side.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def intensity_histogram(original: np.ndarray, processed: np.ndarray) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(original.ravel(), bins=64, alpha=0.6, label="original", color="steelblue")
    ax.hist((processed.ravel() * 255).astype(np.uint8), bins=64, alpha=0.6,
            label="CLAHE-enhanced", color="darkorange")
    ax.set_xlabel("pixel intensity (0-255)")
    ax.set_ylabel("pixel count")
    ax.set_title("Pixel-intensity histogram")
    ax.legend()
    path = OUT / "t6_histogram.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def segmentation_overlay(original: np.ndarray, mask: np.ndarray) -> Path:
    """Overlay the segmentation mask's boundary as a colored contour on the
    original image, plus the mask itself for reference."""
    contours = measure.find_contours(mask.astype(float), level=0.5)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(original, cmap="gray")
    for contour in contours:
        ax.plot(contour[:, 1], contour[:, 0], color="red", linewidth=1.5)
    ax.set_title(f"Otsu segmentation boundary overlay ({len(contours)} regions)")
    ax.axis("off")
    path = OUT / "t6_segmentation_overlay.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def main():
    OUT.mkdir(exist_ok=True)
    original = data.cell()
    processed = exposure.equalize_adapthist(original, clip_limit=0.03)
    thresh = filters.threshold_otsu(original)
    mask = original > thresh

    p1 = side_by_side(original, processed)
    p2 = intensity_histogram(original, processed)
    p3 = segmentation_overlay(original, mask)

    print(f"Saved: {p1.name}, {p2.name}, {p3.name}")

    # --- self-check ---
    for path in (p1, p2, p3):
        assert path.exists() and path.stat().st_size > 0, f"missing or empty output: {path.name}"
    assert original.shape == processed.shape, "processed image should match original shape"
    assert 0.0 < mask.mean() < 1.0, "segmentation mask should be neither empty nor full"
    print("\nT6 self-check passed.")


if __name__ == "__main__":
    main()
