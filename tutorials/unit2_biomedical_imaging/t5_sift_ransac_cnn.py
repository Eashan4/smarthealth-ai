"""T5: Biomedical Image Analysis Techniques -- SIFT, RANSAC, CNN.
Course: 21CSE428T Healthcare Analytics, Unit 2.

Feature detector: skimage.feature.SIFT (available since scikit-image 0.19,
confirmed present in this venv's scikit-image==0.24 -- see README for the
ORB fallback note). RANSAC robustly fits an affine transform between two
views of the same biomedical image and rejects outlier keypoint matches.
The CNN section trains a tiny torch conv-net on a synthetic patch dataset
built from the sample image (torchvision is not installed in this venv, so
no torchvision.datasets download is used -- see README).

Usage: python t5_sift_ransac_cnn.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from skimage import data, transform, util

try:
    from skimage.feature import SIFT as FeatureDetector
    DETECTOR_NAME = "SIFT"
except ImportError:  # scikit-image < 0.19
    from skimage.feature import ORB as FeatureDetector
    DETECTOR_NAME = "ORB"

from skimage.feature import match_descriptors, plot_matches
from skimage.measure import ransac
from skimage.transform import AffineTransform

OUT = Path(__file__).parent / "outputs"


def detect_keypoints(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Run SIFT (or ORB fallback) and return (keypoints, descriptors)."""
    detector = FeatureDetector()
    detector.detect_and_extract(image)
    return detector.keypoints, detector.descriptors


def sift_visualization(image: np.ndarray, keypoints: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(image, cmap="gray")
    ax.scatter(keypoints[:, 1], keypoints[:, 0], s=15, facecolors="none", edgecolors="r")
    ax.set_title(f"{DETECTOR_NAME} keypoints ({len(keypoints)} found)")
    ax.axis("off")
    fig.savefig(OUT / "t5_keypoints.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def ransac_demo(image: np.ndarray) -> int:
    """Create a rotated+shifted copy of the image, match keypoints between
    the two, then use RANSAC to fit an affine transform and separate inlier
    matches (consistent with the true transform) from outlier matches."""
    true_tform = AffineTransform(rotation=np.deg2rad(12), translation=(15, -10))
    warped = transform.warp(image, true_tform.inverse, output_shape=image.shape,
                             preserve_range=True).astype(image.dtype)

    kp1, desc1 = detect_keypoints(image)
    kp2, desc2 = detect_keypoints(warped)

    # cross_check=False, max_ratio<1 keeps some ambiguous/wrong matches in
    # the pool so RANSAC actually has outliers to reject (a strict
    # cross-check on this small, low-texture sample image tends to yield
    # only correct matches, which makes for a less illustrative demo).
    matches = match_descriptors(desc1, desc2, cross_check=False, max_ratio=0.9)
    src = kp1[matches[:, 0]][:, ::-1]  # (row, col) -> (x, y)
    dst = kp2[matches[:, 1]][:, ::-1]

    model, inliers = ransac((src, dst), AffineTransform, min_samples=3,
                             residual_threshold=3, max_trials=1000, rng=0)
    n_inliers = int(inliers.sum())

    fig, ax = plt.subplots(figsize=(10, 6))
    plot_matches(ax, image, warped, kp1, kp2, matches[inliers], matches_color="g")
    ax.set_title(f"RANSAC inlier matches: {n_inliers}/{len(matches)} "
                 f"(estimated rotation={np.rad2deg(model.rotation):.1f} deg)")
    ax.axis("off")
    fig.savefig(OUT / "t5_ransac_matches.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    print(f"RANSAC: {n_inliers}/{len(matches)} matches kept as inliers; "
          f"true rotation=12.0 deg, estimated={np.rad2deg(model.rotation):.1f} deg")
    return n_inliers


# --- tiny CNN over a synthetic patch dataset (no torchvision needed) ---

class TinyCNN(nn.Module):
    def __init__(self, num_classes: int = 2):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 8, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(8, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(16 * 8 * 8, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


def build_patch_dataset(image: np.ndarray, patch_size: int = 32,
                         n_per_class: int = 60, rng: np.random.Generator = None
                         ) -> tuple[torch.Tensor, torch.Tensor]:
    """Class 0: plain crops of the sample image. Class 1: the same crops
    rotated 90deg + flipped, i.e. an easy but real (non-trivial) texture-
    orientation classification task built entirely from one image."""
    rng = rng or np.random.default_rng(0)
    img = util.img_as_float(image)
    h, w = img.shape
    patches, labels = [], []
    for _ in range(n_per_class):
        y = rng.integers(0, h - patch_size)
        x = rng.integers(0, w - patch_size)
        crop = img[y:y + patch_size, x:x + patch_size]
        patches.append(crop)
        labels.append(0)

        y = rng.integers(0, h - patch_size)
        x = rng.integers(0, w - patch_size)
        crop = img[y:y + patch_size, x:x + patch_size]
        crop = np.rot90(crop, k=1).copy()
        crop = np.fliplr(crop).copy()
        patches.append(crop)
        labels.append(1)

    X = torch.tensor(np.stack(patches), dtype=torch.float32).unsqueeze(1)  # [N,1,H,W]
    y = torch.tensor(labels, dtype=torch.long)
    return X, y


def train_tiny_cnn(X: torch.Tensor, y: torch.Tensor, epochs: int = 60) -> list[float]:
    """Full-batch Adam on 75% of the patches; accuracy is reported on the 25% the network never trained on."""
    torch.manual_seed(0)
    perm = torch.randperm(len(y))
    n_tr = int(0.75 * len(y))
    tr, te = perm[:n_tr], perm[n_tr:]
    model = TinyCNN(num_classes=2)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    loss_fn = nn.CrossEntropyLoss()

    losses = []
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(X[tr]), y[tr])
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
        if epoch % 10 == 0 or epoch == epochs - 1:
            print(f"  epoch {epoch + 1}/{epochs}: loss={loss.item():.4f}")

    with torch.no_grad():
        acc_tr = (model(X[tr]).argmax(1) == y[tr]).float().mean().item()
        acc_te = (model(X[te]).argmax(1) == y[te]).float().mean().item()
    print(f"CNN: train accuracy {acc_tr * 100:.1f}% ({len(tr)} patches), held-out accuracy {acc_te * 100:.1f}% ({len(te)} patches)")
    return losses


def cnn_visualization(X: torch.Tensor, y: torch.Tensor, losses: list[float]) -> None:
    fig, axes = plt.subplots(1, 5, figsize=(14, 3))
    for i, ax in enumerate(axes):
        ax.imshow(X[i, 0].numpy(), cmap="gray")
        ax.set_title(f"label={y[i].item()}")
        ax.axis("off")
    fig.suptitle("Sample CNN training patches (0=plain crop, 1=rotated+flipped)")
    fig.savefig(OUT / "t5_cnn_patches.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(losses, marker="o")
    ax.set_xlabel("epoch")
    ax.set_ylabel("training loss")
    ax.set_title("Tiny CNN training loss")
    fig.savefig(OUT / "t5_cnn_loss.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    image = data.cell()
    print(f"Feature detector in use: {DETECTOR_NAME}")

    keypoints, _ = detect_keypoints(image)
    sift_visualization(image, keypoints)
    print(f"{DETECTOR_NAME}: detected {len(keypoints)} keypoints")

    n_inliers = ransac_demo(image)

    X, y = build_patch_dataset(image)
    losses = train_tiny_cnn(X, y)
    cnn_visualization(X, y, losses)

    # --- self-check ---
    expected_files = ["t5_keypoints.png", "t5_ransac_matches.png",
                       "t5_cnn_patches.png", "t5_cnn_loss.png"]
    for fname in expected_files:
        fpath = OUT / fname
        assert fpath.exists() and fpath.stat().st_size > 0, f"missing or empty output: {fname}"

    assert len(keypoints) > 0, f"{DETECTOR_NAME} should find at least one keypoint"
    assert n_inliers >= 5, f"RANSAC should find a reasonable number of inliers, got {n_inliers}"
    assert losses[-1] < losses[0], "CNN training loss should decrease over epochs"
    print("\nT5 self-check passed.")


if __name__ == "__main__":
    main()
