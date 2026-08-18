"""LSTM -- comparison model against the primary 1D CNN (docs/DOCUMENTATION.md
sec 6.2/6.3). Same segmented input, used purely for sequence-learning
comparison; not the deployed model unless the measured comparison favors it.
"""

from __future__ import annotations

import torch
import torch.nn as nn


class ActivityLSTM(nn.Module):
    def __init__(self, num_channels: int, num_classes: int,
                 hidden_size: int = 64, num_layers: int = 1, dropout: float = 0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=num_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_size, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, T, C]
        out, (h_n, _) = self.lstm(x)
        last_hidden = h_n[-1]  # [B, hidden_size]
        return self.classifier(last_hidden)
