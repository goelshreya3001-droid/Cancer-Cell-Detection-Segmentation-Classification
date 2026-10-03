"""
Neural network architecture definitions.

Extracted verbatim from:
  - 02_train_unet.ipynb  (UNet, DoubleConv)
  - 04_nuclei_classification.ipynb  (NucleiClassifier)

DO NOT modify these architectures — they must match the saved weights exactly.
"""

import torch
import torch.nn as nn


# ---------------------------------------------------------------------------
# U-Net (segmentation)  — source: 02_train_unet.ipynb
# ---------------------------------------------------------------------------

class DoubleConv(nn.Module):
    """Two back-to-back Conv2d → BatchNorm2d → ReLU blocks."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class UNet(nn.Module):
    """
    4-level encoder-decoder U-Net with skip connections.

    Input:  (B, 3, H, W)  — RGB float32 in [0, 1], H and W must be multiples of 16
    Output: (B, 1, H, W)  — raw logits; apply sigmoid → probability map
    Threshold at 0.5 to get a binary nuclei mask.
    """

    def __init__(self, in_channels: int = 3, out_channels: int = 1):
        super().__init__()
        # Encoder
        self.inc   = DoubleConv(in_channels, 32)
        self.down1 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(32, 64))
        self.down2 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(64, 128))
        self.down3 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(128, 256))
        self.down4 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(256, 512))

        # Decoder
        self.up1      = nn.ConvTranspose2d(512, 256, kernel_size=2, stride=2)
        self.conv_up1 = DoubleConv(512, 256)
        self.up2      = nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2)
        self.conv_up2 = DoubleConv(256, 128)
        self.up3      = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
        self.conv_up3 = DoubleConv(128, 64)
        self.up4      = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
        self.conv_up4 = DoubleConv(64, 32)

        self.outc = nn.Conv2d(32, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)

        x = self.up1(x5)
        x = self.conv_up1(torch.cat([x, x4], dim=1))
        x = self.up2(x)
        x = self.conv_up2(torch.cat([x, x3], dim=1))
        x = self.up3(x)
        x = self.conv_up3(torch.cat([x, x2], dim=1))
        x = self.up4(x)
        x = self.conv_up4(torch.cat([x, x1], dim=1))

        return self.outc(x)


# ---------------------------------------------------------------------------
# NucleiClassifier (per-nucleus classification)  — source: 04_nuclei_classification.ipynb
# ---------------------------------------------------------------------------

class NucleiClassifier(nn.Module):
    """
    Lightweight 3-layer CNN for single-nucleus phenotype classification.

    Input:  (B, 3, 32, 32) — RGB float32 in [0, 1], 32×32 nucleus crop
    Output: (B, 5)          — raw logits for 5 phenotype classes

    Class scheme (matches CoNSeP label convention, 0-indexed):
        0 — Miscellaneous / Other
        1 — Inflammatory  (lymphocytes, plasma cells)
        2 — Healthy Epithelial
        3 — Malignant Epithelial  ← key clinical target
        4 — Spindle / Stromal
    """

    def __init__(self, num_classes: int = 5):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = torch.flatten(x, 1)
        return self.classifier(x)
