"""1D CNN -- primary model for activity/fall time-series classification.

Baseline block per docs/DOCUMENTATION.md sec 6.1:
Conv1D -> BatchNorm -> ReLU -> MaxPool (x2) -> GlobalPool -> Dense -> Dropout -> Softmax.
Filter counts/kernel sizes/depth are experimental starting points, tuned in
ml/training/train.py's sweep -- not a claimed optimum.
"""

from __future__ import annotations

import torch
import torch.nn as nn


class ActivityCNN(nn.Module):
    def __init__(self, num_channels: int, num_classes: int,
                 filters: tuple[int, int] = (32, 64), kernel_size: int = 5,
                 dropout: float = 0.3):
        super().__init__()
        f1, f2 = filters
        pad = kernel_size // 2
        self.features = nn.Sequential(
            nn.Conv1d(num_channels, f1, kernel_size, padding=pad),
            nn.BatchNorm1d(f1),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(f1, f2, kernel_size, padding=pad),
            nn.BatchNorm1d(f2),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(f2, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, T, C] -> Conv1d expects [B, C, T]
        x = x.transpose(1, 2)
        x = self.features(x)
        x = self.global_pool(x)
        return self.classifier(x)
