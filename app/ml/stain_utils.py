"""
Macenko H&E stain normalization utility.

Extracted verbatim from stain_utils.ipynb — DO NOT modify.

Corrects color variations introduced by different scanners and staining
protocols using optical density (OD) decomposition.
"""

import numpy as np


class MacenkoNormalizer:
    """
    Normalizes H&E histopathology images using the Macenko method.

    Calibrated reference vectors (HERef, maxCRef) were set in the
    original notebook to represent a canonical CoNSeP stain appearance.

    Usage:
        normalizer = MacenkoNormalizer()
        norm_rgb = normalizer.normalize(img_rgb)   # img_rgb: uint8 H×W×3
    """

    def __init__(self):
        # Calibrated H&E reference vectors — source: stain_utils.ipynb
        self.HERef = np.array([
            [0.5626, 0.2159],
            [0.7201, 0.8012],
            [0.4062, 0.5581],
        ])
        self.maxCRef = np.array([1.9705, 1.0308])

    def normalize(
        self,
        img_rgb: np.ndarray,
        Io: float = 240,
        alpha: float = 1,
        beta: float = 0.15,
    ) -> np.ndarray:
        """
        Normalize a single RGB image.

        Args:
            img_rgb: uint8 numpy array of shape (H, W, 3).
            Io:      Transmitted light intensity reference (default 240).
            alpha:   Percentile for robust angle estimation (default 1).
            beta:    Optical density threshold to exclude background (default 0.15).

        Returns:
            Normalized uint8 RGB image of the same shape.
            Falls back to the original image if the slide is blank/empty.
        """
        h, w, c = img_rgb.shape
        img = img_rgb.reshape((-1, 3)).astype(float)

        # 1. Optical Density (OD) calculation
        OD = -np.log((img + 1.0) / Io)
        ODhat = OD[~np.any(OD < beta, axis=1)]

        if len(ODhat) == 0:
            # Fallback for empty / near-blank tissue regions
            return img_rgb

        # 2. Covariance eigenvectors
        _, eigvecs = np.linalg.eigh(np.cov(ODhat, rowvar=False))
        That = ODhat.dot(eigvecs[:, 1:3])

        phi = np.arctan2(That[:, 1], That[:, 0])
        minPhi = np.percentile(phi, alpha)
        maxPhi = np.percentile(phi, 100 - alpha)

        vMin = eigvecs[:, 1:3].dot(
            np.array([np.cos(minPhi), np.sin(minPhi)])
        )
        vMax = eigvecs[:, 1:3].dot(
            np.array([np.cos(maxPhi), np.sin(maxPhi)])
        )

        HE = (
            np.array((vMin, vMax)).T
            if vMin[0] > vMax[0]
            else np.array((vMax, vMin)).T
        )

        # 3. Concentrations & reference scaling
        Y = np.reshape(OD, (-1, 3)).T
        C = np.linalg.lstsq(HE, Y, rcond=None)[0]
        maxC = np.percentile(C, 99, axis=1)

        C = C / maxC[:, None]
        C = C * self.maxCRef[:, None]

        # 4. Reconstruct normalized RGB
        norm_img = Io * np.exp(-self.HERef.dot(C))
        norm_img = np.clip(norm_img.T, 0, 255).astype(np.uint8)
        return norm_img.reshape((h, w, c))
