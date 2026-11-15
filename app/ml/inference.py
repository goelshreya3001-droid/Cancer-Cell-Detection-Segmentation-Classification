"""
Flask-compatible inference pipeline using the ML developer's latest pipeline.

Preserved backend API:
    load_models()
    run_inference(...)

The model architecture and state-dict loading remain unchanged.
"""

import os
import time
import logging
from pathlib import Path
from collections import Counter
from typing import Any

# Must be set before importing torch on some Windows/Anaconda setups.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import cv2
import numpy as np
import torch
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

from .models import UNet, NucleiClassifier
from .stain_utils import MacenkoNormalizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths and class definitions
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNET_WEIGHTS_PATH = _PROJECT_ROOT / "models" / "unet.pth"
CLASSIFIER_WEIGHTS_PATH = _PROJECT_ROOT / "models" / "classifier.pth"

CLASS_NAMES = {
    0: "Other",
    1: "Inflammatory",
    2: "Healthy Epithelial",
    3: "Malignant Epithelial",
    4: "Stromal",
}

# Exact BGR colors supplied by the ML developer.
CLASS_COLORS_BGR = {
    0: (140, 140, 140),  # Grey - Other
    1: (255, 0, 0),      # Blue - Inflammatory
    2: (0, 255, 0),      # Green - Healthy Epithelial
    3: (0, 0, 255),      # Red - Malignant / Dysplastic
    4: (255, 0, 255),    # Magenta/Pink - Stromal
}

PATCH_SIZE = 256
UNET_THRESHOLD = 0.5
MIN_DISTANCE = 3
MIN_INSTANCE_PIXELS = 8
CROP_SIZE = 32

# ---------------------------------------------------------------------------
# Singleton model state
# ---------------------------------------------------------------------------

_models: dict[str, Any] = {}
_normalizer = MacenkoNormalizer()
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Model loading - existing backend implementation preserved
# ---------------------------------------------------------------------------

def load_models() -> None:
    """Load the U-Net and classifier state dictionaries once."""
    global _models, _device

    if _models:
        logger.debug("Models already loaded - skipping.")
        return

    logger.info("Loading models on device: %s", _device)

    if not UNET_WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"U-Net weights not found at: {UNET_WEIGHTS_PATH}"
        )

    unet = UNet(in_channels=3, out_channels=1).to(_device)
    unet.load_state_dict(
        torch.load(
            str(UNET_WEIGHTS_PATH),
            map_location=_device,
            weights_only=True,
        ),
        strict=True,
    )
    unet.eval()
    logger.info("U-Net loaded from %s", UNET_WEIGHTS_PATH)

    if not CLASSIFIER_WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Classifier weights not found at: {CLASSIFIER_WEIGHTS_PATH}"
        )

    classifier = NucleiClassifier(num_classes=5).to(_device)
    classifier.load_state_dict(
        torch.load(
            str(CLASSIFIER_WEIGHTS_PATH),
            map_location=_device,
            weights_only=True,
        ),
        strict=True,
    )
    classifier.eval()
    logger.info("NucleiClassifier loaded from %s", CLASSIFIER_WEIGHTS_PATH)

    _models["unet"] = unet
    _models["classifier"] = classifier
    logger.info("Both models ready.")


# ---------------------------------------------------------------------------
# Stage 1 - Full-resolution tiled U-Net segmentation (developer's logic)
# ---------------------------------------------------------------------------

def _predict_segmentation(img_rgb: np.ndarray) -> np.ndarray:
    """Run U-Net on 256x256 tiles and return a binary mask."""
    unet = _models["unet"]
    orig_h, orig_w, _ = img_rgb.shape
    full_mask = np.zeros((orig_h, orig_w), dtype=np.float32)

    for y in range(0, orig_h, PATCH_SIZE):
        for x in range(0, orig_w, PATCH_SIZE):
            y_end = min(y + PATCH_SIZE, orig_h)
            x_end = min(x + PATCH_SIZE, orig_w)
            patch = img_rgb[y:y_end, x:x_end]

            pad_h = PATCH_SIZE - patch.shape[0]
            pad_w = PATCH_SIZE - patch.shape[1]
            if pad_h > 0 or pad_w > 0:
                # Match developer code. Replicate is a safe fallback for
                # one-pixel dimensions where REFLECT padding is not suitable.
                border_type = (
                    cv2.BORDER_REFLECT
                    if patch.shape[0] > 1 and patch.shape[1] > 1
                    else cv2.BORDER_REPLICATE
                )
                patch = cv2.copyMakeBorder(
                    patch, 0, pad_h, 0, pad_w, border_type
                )

            tensor_patch = (
                torch.from_numpy(patch)
                .permute(2, 0, 1)
                .float()
                .div(255.0)
                .unsqueeze(0)
                .to(_device)
            )

            with torch.no_grad():
                prediction = (
                    torch.sigmoid(unet(tensor_patch))
                    .squeeze()
                    .cpu()
                    .numpy()
                )

            full_mask[y:y_end, x:x_end] = prediction[
                : y_end - y, : x_end - x
            ]

    return (full_mask > UNET_THRESHOLD).astype(np.uint8)


# ---------------------------------------------------------------------------
# Stage 2 - Watershed and developer's centre-based 32x32 crop extraction
# ---------------------------------------------------------------------------

def _separate_nuclei(
    img_rgb: np.ndarray,
    binary_mask: np.ndarray,
) -> tuple[np.ndarray, list[dict]]:
    """Separate instances and create 32x32 RGB crops scaled only by /255."""
    orig_h, orig_w, _ = img_rgb.shape

    distance = ndi.distance_transform_edt(binary_mask)
    coords = peak_local_max(
        distance,
        min_distance=MIN_DISTANCE,
        labels=binary_mask,
    )

    if len(coords) == 0:
        return np.zeros((orig_h, orig_w), dtype=np.int32), []

    mask_peaks = np.zeros(distance.shape, dtype=bool)
    mask_peaks[tuple(coords.T)] = True
    markers, _ = ndi.label(mask_peaks)
    labels = watershed(-distance, markers, mask=binary_mask.astype(bool))

    nuclei: list[dict] = []

    for label_id in np.unique(labels):
        if label_id == 0:
            continue

        instance_mask = (labels == label_id).astype(np.uint8)
        ys, xs = np.where(instance_mask == 1)

        if len(xs) < MIN_INSTANCE_PIXELS:
            continue

        # Match the developer's crop: 32x32 around the instance centroid.
        cy, cx = int(np.mean(ys)), int(np.mean(xs))
        y1, y2 = max(0, cy - 16), min(orig_h, cy + 16)
        x1, x2 = max(0, cx - 16), min(orig_w, cx + 16)

        crop = img_rgb[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        if crop.shape[0] != CROP_SIZE or crop.shape[1] != CROP_SIZE:
            crop = cv2.resize(crop, (CROP_SIZE, CROP_SIZE))

        # Developer's new classifier preprocessing: ToTensor equivalent,
        # with values scaled to [0, 1]; no ImageNet mean/std normalization.
        crop_tensor = (
            torch.from_numpy(crop.copy())
            .permute(2, 0, 1)
            .float()
            .div(255.0)
        )

        nuclei.append({
            "crop": crop_tensor,
            "instance_mask": instance_mask,
            "bbox": (
                int(xs.min()), int(ys.min()),
                int(xs.max()), int(ys.max()),
            ),
            "area": int(len(xs)),
        })

    return labels, nuclei


# ---------------------------------------------------------------------------
# Stage 3 - Batch classification (developer's argmax logic)
# ---------------------------------------------------------------------------

def _classify_nuclei(
    nuclei: list[dict],
    batch_size: int = 64,
) -> list[int]:
    """Classify crops using softmax argmax, with no malignant override."""
    if not nuclei:
        return []

    classifier = _models["classifier"]
    crops = torch.stack([nucleus["crop"] for nucleus in nuclei])
    predictions: list[int] = []

    with torch.no_grad():
        for start in range(0, len(crops), batch_size):
            batch = crops[start:start + batch_size].to(_device)
            logits = classifier(batch)
            probabilities = torch.softmax(logits, dim=1)
            batch_predictions = torch.argmax(probabilities, dim=1)
            predictions.extend(
                int(class_id) for class_id in batch_predictions.cpu().tolist()
            )

    return predictions


# ---------------------------------------------------------------------------
# Overlay generation - developer's instance-contour overlay
# ---------------------------------------------------------------------------

def _draw_overlay(
    img_rgb: np.ndarray,
    nuclei: list[dict],
    class_ids: list[int],
) -> np.ndarray:
    """Draw class-colored instance contours and return an RGB image."""
    overlay_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR).copy()

    for nucleus, class_id in zip(nuclei, class_ids):
        contours, _ = cv2.findContours(
            nucleus["instance_mask"],
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        cv2.drawContours(
            overlay_bgr,
            contours,
            -1,
            CLASS_COLORS_BGR[class_id],
            2,
        )

    return cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Public API - Flask backend contract preserved
# ---------------------------------------------------------------------------

def run_inference(
    image_path: str,
    apply_stain_normalization: bool = False,
    save_overlay_path: str | None = None,
    save_mask_path: str | None = None,
) -> dict:
    """
    Run the developer's final pipeline while preserving Flask's dictionary
    response keys and the existing run_inference function signature.
    """
    if not _models:
        raise RuntimeError(
            "Models not loaded. Call load_models() before run_inference()."
        )

    image_path = str(image_path)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    start_time = time.perf_counter()

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Image could not be loaded: {image_path}")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Keep the existing optional backend feature; it remains off by default.
    if apply_stain_normalization:
        try:
            img_rgb = _normalizer.normalize(img_rgb)
            logger.debug("Macenko stain normalization applied.")
        except Exception as exc:
            logger.warning(
                "Stain normalization failed (%s) - using raw image.", exc
            )

    logger.info("Running U-Net segmentation...")
    binary_mask = _predict_segmentation(img_rgb)

    logger.info("Running watershed separation...")
    _, nuclei = _separate_nuclei(img_rgb, binary_mask)

    logger.info("Classifying %d nuclei...", len(nuclei))
    class_ids = _classify_nuclei(nuclei)

    prediction_counts = Counter(class_ids)
    counts = {
        class_id: prediction_counts.get(class_id, 0)
        for class_id in range(5)
    }

    logger.info(
        "Classifier class distribution: %s",
        {
            CLASS_NAMES[class_id]: counts[class_id]
            for class_id in range(5)
        },
    )

    nuclei_details = [
        {
            "bbox": nucleus["bbox"],
            "class_id": class_id,
            "class_name": CLASS_NAMES[class_id],
            "area": nucleus["area"],
        }
        for nucleus, class_id in zip(nuclei, class_ids)
    ]

    overlay = _draw_overlay(img_rgb, nuclei, class_ids)

    if save_overlay_path:
        overlay_dir = os.path.dirname(save_overlay_path)
        if overlay_dir:
            os.makedirs(overlay_dir, exist_ok=True)
        cv2.imwrite(
            save_overlay_path,
            cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR),
        )
        logger.info("Overlay saved to %s", save_overlay_path)

    if save_mask_path:
        mask_dir = os.path.dirname(save_mask_path)
        if mask_dir:
            os.makedirs(mask_dir, exist_ok=True)
        cv2.imwrite(
            save_mask_path,
            (binary_mask * 255).astype(np.uint8),
        )
        logger.info("Mask saved to %s", save_mask_path)

    elapsed = time.perf_counter() - start_time
    total_nuclei = len(class_ids)

    logger.info(
        "Inference complete in %.2f s - %d nuclei found.",
        elapsed,
        total_nuclei,
    )

    return {
        "overlay_image": overlay,
        "mask_image": binary_mask,
        "total_nuclei": total_nuclei,
        "malignant_count": counts[3],
        "inflammatory_count": counts[1],
        "healthy_count": counts[2],
        "stromal_count": counts[4],
        "other_count": counts[0],
        "nuclei_details": nuclei_details,
        "processing_time_sec": round(elapsed, 2),
    }
