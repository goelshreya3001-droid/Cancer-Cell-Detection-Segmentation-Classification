"""
Core ML inference pipeline.

Assembles the full two-stage pipeline extracted from:
  - 03_evaluate_unet.ipynb     (separate_and_extract_nuclei, sliding-window)
  - evaluate_generalization.ipynb (predict_large_image)
  - 04_nuclei_classification.ipynb (per-nucleus classification)

Public API:
    load_models()          — loads both models once at startup
    run_inference(...)     — runs the full pipeline on one image

DO NOT modify model architectures or weight-loading logic.
"""

import os
import time
import logging
from pathlib import Path

# Suppress Anaconda + PyTorch OpenMP DLL conflict on Windows.
# This must be set BEFORE torch is imported.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
from typing import Any

import cv2
import numpy as np
import torch
from scipy import ndimage
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

from .models import UNet, NucleiClassifier
from .stain_utils import MacenkoNormalizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Paths to trained weights (relative to project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]   # .../Cancer-Cell-...
UNET_WEIGHTS_PATH = _PROJECT_ROOT / "models" / "unet.pth"
CLASSIFIER_WEIGHTS_PATH = _PROJECT_ROOT / "models" / "classifier.pth"

# Nucleus class labels — must match 04_nuclei_classification.ipynb exactly
CLASS_NAMES = {
    0: "Other",
    1: "Inflammatory",
    2: "Healthy Epithelial",
    3: "Malignant Epithelial",
    4: "Stromal",
}

# BGR colors for overlay drawing (OpenCV convention)
CLASS_COLORS_BGR = {
    0: (128, 128, 128),   # Gray  — Other/Misc
    1: (200, 100,   0),   # Blue  — Inflammatory
    2: (0,   200,  50),   # Green — Healthy Epithelial
    3: (0,    0,  220),   # Red   — Malignant Epithelial
    4: (0,   200, 220),   # Yellow — Stromal
}

# Processing constants — must match notebook values
PATCH_SIZE    = 256   # U-Net input tile size
STRIDE        = 128   # Sliding-window stride for large images
UNET_THRESH   = 0.5   # Binary mask threshold
MIN_DISTANCE  = 7     # Watershed: min distance between nucleus peaks
MIN_AREA      = 30    # Watershed: minimum nucleus area in pixels
CROP_SIZE     = 32    # CNN input: nucleus crop size
CROP_PADDING  = 4     # Padding around each nucleus bounding box

# ---------------------------------------------------------------------------
# Singleton model state
# ---------------------------------------------------------------------------

_models: dict[str, Any] = {}   # populated by load_models()
_normalizer = MacenkoNormalizer()
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_models() -> None:
    """
    Load both U-Net and NucleiClassifier from disk into memory.

    Call this once at application startup. Models are stored in the
    module-level `_models` dict and reused for every subsequent inference.

    Raises:
        FileNotFoundError: if weight files are missing.
    """
    global _models, _device

    if _models:
        logger.debug("Models already loaded — skipping.")
        return

    logger.info("Loading models on device: %s", _device)

    # --- U-Net ---
    if not UNET_WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"U-Net weights not found at: {UNET_WEIGHTS_PATH}\n"
            "Make sure models/unet.pth is present in the project root."
        )
    unet = UNet(in_channels=3, out_channels=1).to(_device)
    unet.load_state_dict(
        torch.load(str(UNET_WEIGHTS_PATH), map_location=_device, weights_only=True)
    )
    unet.eval()
    logger.info("U-Net loaded from %s", UNET_WEIGHTS_PATH)

    # --- NucleiClassifier ---
    if not CLASSIFIER_WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Classifier weights not found at: {CLASSIFIER_WEIGHTS_PATH}\n"
            "Make sure models/classifier.pth is present in the project root."
        )
    classifier = NucleiClassifier(num_classes=5).to(_device)
    classifier.load_state_dict(
        torch.load(str(CLASSIFIER_WEIGHTS_PATH), map_location=_device, weights_only=True)
    )
    classifier.eval()
    logger.info("NucleiClassifier loaded from %s", CLASSIFIER_WEIGHTS_PATH)

    _models["unet"] = unet
    _models["classifier"] = classifier
    logger.info("Both models ready.")


# ---------------------------------------------------------------------------
# Stage 1 — Segmentation: sliding-window U-Net inference
# ---------------------------------------------------------------------------

def _predict_segmentation(img_rgb: np.ndarray) -> np.ndarray:
    """
    Run U-Net over the full image using overlapping sliding-window tiling.

    Extracted from evaluate_generalization.ipynb → predict_large_image().

    Args:
        img_rgb: uint8 RGB array (H, W, 3). Any size supported.

    Returns:
        Binary mask (H, W) uint8, values 0 or 1.
    """
    unet = _models["unet"]
    h, w, _ = img_rgb.shape
    prob_map  = np.zeros((h, w), dtype=np.float32)
    count_map = np.zeros((h, w), dtype=np.float32)

    # For small images (≤ PATCH_SIZE), process as single tile
    if h <= PATCH_SIZE and w <= PATCH_SIZE:
        # Pad to PATCH_SIZE if needed so U-Net dimensions are multiples of 16
        pad_h = PATCH_SIZE - h
        pad_w = PATCH_SIZE - w
        padded = np.pad(img_rgb, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
        patch = padded.astype(np.float32) / 255.0
        t = torch.tensor(patch.transpose(2, 0, 1)).unsqueeze(0).to(_device)
        with torch.no_grad():
            pred = torch.sigmoid(unet(t)).squeeze().cpu().numpy()
        prob_map  = pred[:h, :w]
        count_map = np.ones((h, w), dtype=np.float32)
    else:
        # Sliding-window tiling (source: evaluate_generalization.ipynb)
        for y in range(0, max(1, h - PATCH_SIZE + 1), STRIDE):
            for x in range(0, max(1, w - PATCH_SIZE + 1), STRIDE):
                y_end = min(y + PATCH_SIZE, h)
                x_end = min(x + PATCH_SIZE, w)
                y_start = y_end - PATCH_SIZE
                x_start = x_end - PATCH_SIZE

                patch = img_rgb[y_start:y_end, x_start:x_end].astype(np.float32) / 255.0
                t = torch.tensor(patch.transpose(2, 0, 1)).unsqueeze(0).to(_device)
                with torch.no_grad():
                    pred = torch.sigmoid(unet(t)).squeeze().cpu().numpy()
                prob_map[y_start:y_end, x_start:x_end]  += pred
                count_map[y_start:y_end, x_start:x_end] += 1.0

        count_map[count_map == 0] = 1.0

    final_prob = prob_map / count_map
    return (final_prob > UNET_THRESH).astype(np.uint8)


# ---------------------------------------------------------------------------
# Stage 2 — Instance separation: Watershed post-processing
# ---------------------------------------------------------------------------

def _separate_nuclei(
    raw_img: np.ndarray,
    binary_mask: np.ndarray,
) -> tuple[np.ndarray, list[dict]]:
    """
    Separate touching nuclei using distance transform + watershed.

    Extracted from 03_evaluate_unet.ipynb → separate_and_extract_nuclei().

    Args:
        raw_img:     uint8 RGB array (H, W, 3).
        binary_mask: uint8 array (H, W), values 0 or 1.

    Returns:
        labels:  (H, W) int32 watershed label array (0 = background).
        nuclei:  list of dicts, each with keys:
                   crop  — (C, H, C) float32 tensor ready for classifier
                   bbox  — (x_min, y_min, x_max, y_max) in pixel coords
                   area  — nucleus area in pixels
    """
    h, w, _ = raw_img.shape

    # 1. Distance transform
    dist_map = cv2.distanceTransform(
        (binary_mask * 255).astype(np.uint8), cv2.DIST_L2, 5
    )

    # 2. Local maxima → nucleus centres
    coordinates = peak_local_max(
        dist_map, min_distance=MIN_DISTANCE, labels=binary_mask.astype(bool)
    )

    if len(coordinates) == 0:
        return np.zeros((h, w), dtype=np.int32), []

    # 3. Watershed markers
    markers = np.zeros(dist_map.shape, dtype=np.int32)
    for idx, (r, c) in enumerate(coordinates, start=1):
        markers[r, c] = idx
    markers = ndimage.label(markers)[0]

    # 4. Watershed assignment
    labels = watershed(-dist_map, markers, mask=binary_mask.astype(bool))

    # 5. Extract per-nucleus crops + bounding boxes
    nuclei: list[dict] = []
    for label_id in np.unique(labels):
        if label_id == 0:
            continue

        nucleus_area = int(np.sum(labels == label_id))
        if nucleus_area < MIN_AREA:
            continue

        coords = np.where(labels == label_id)
        y_min, y_max = int(np.min(coords[0])), int(np.max(coords[0]))
        x_min, x_max = int(np.min(coords[1])), int(np.max(coords[1]))

        # 4px padding (source: 03_evaluate_unet.ipynb)
        y_pad_min = max(0, y_min - CROP_PADDING)
        y_pad_max = min(h, y_max + CROP_PADDING)
        x_pad_min = max(0, x_min - CROP_PADDING)
        x_pad_max = min(w, x_max + CROP_PADDING)

        crop = raw_img[y_pad_min:y_pad_max, x_pad_min:x_pad_max]
        if crop.size == 0:
            continue

        # Resize to 32×32 and normalise — source: 04_nuclei_classification.ipynb
        crop_resized = cv2.resize(crop, (CROP_SIZE, CROP_SIZE))
        crop_norm = crop_resized.astype(np.float32) / 255.0
        crop_tensor = torch.tensor(
            crop_norm.transpose(2, 0, 1), dtype=torch.float32
        )  # (3, 32, 32)

        nuclei.append({
            "crop":  crop_tensor,
            "bbox":  (x_min, y_min, x_max, y_max),
            "area":  nucleus_area,
        })

    return labels, nuclei


# ---------------------------------------------------------------------------
# Stage 3 — Classification: batch CNN forward pass
# ---------------------------------------------------------------------------

def _classify_nuclei(nuclei: list[dict], batch_size: int = 64) -> list[int]:
    """
    Run NucleiClassifier on all extracted nucleus crops.

    Args:
        nuclei:     list of nucleus dicts from _separate_nuclei().
        batch_size: number of crops to process per forward pass.

    Returns:
        List of integer class IDs (0–4), one per nucleus.
    """
    if not nuclei:
        return []

    classifier = _models["classifier"]
    all_preds: list[int] = []

    crops = torch.stack([n["crop"] for n in nuclei])  # (N, 3, 32, 32)

    with torch.no_grad():
        for start in range(0, len(crops), batch_size):
            batch = crops[start : start + batch_size].to(_device)
            logits = classifier(batch)
            preds = logits.argmax(dim=1).cpu().tolist()
            all_preds.extend(preds)

    return all_preds


# ---------------------------------------------------------------------------
# Overlay generation
# ---------------------------------------------------------------------------

def _draw_overlay(
    img_rgb: np.ndarray,
    nuclei: list[dict],
    class_ids: list[int],
) -> np.ndarray:
    """
    Draw colored nucleus contours on the original image.

    Color coding:
        Gray   — Other/Misc (class 0)
        Blue   — Inflammatory (class 1)
        Green  — Healthy Epithelial (class 2)
        Red    — Malignant Epithelial (class 3)
        Yellow — Stromal (class 4)

    Args:
        img_rgb:   Original uint8 RGB image.
        nuclei:    List of nucleus dicts (with bbox key).
        class_ids: Predicted class per nucleus.

    Returns:
        Overlay RGB image with nucleus rectangles drawn.
    """
    overlay = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR).copy()

    for nucleus, cls_id in zip(nuclei, class_ids):
        x_min, y_min, x_max, y_max = nucleus["bbox"]
        color = CLASS_COLORS_BGR.get(cls_id, (128, 128, 128))
        cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), color, thickness=2)

    return cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_inference(
    image_path: str,
    apply_stain_normalization: bool = True,
    save_overlay_path: str | None = None,
    save_mask_path: str | None = None,
) -> dict:
    """
    Run the full two-stage pipeline on a single histopathology image.

    Pipeline:
        Input image
        → Macenko stain normalization (optional but recommended)
        → U-Net sliding-window segmentation → binary nuclei mask
        → Watershed instance separation → individual nucleus crops
        → NucleiClassifier (batched) → per-nucleus class IDs
        → Colored overlay image + aggregate counts

    Args:
        image_path:               Absolute or relative path to the input image.
        apply_stain_normalization: Whether to run Macenko normalization first.
        save_overlay_path:        If given, saves overlay image to this path.
        save_mask_path:           If given, saves binary mask image to this path.

    Returns:
        A dict with:
            "overlay_image"      : (H, W, 3) uint8 RGB overlay image
            "mask_image"         : (H, W)    uint8 binary mask (0 or 1)
            "total_nuclei"       : int — total nuclei detected
            "malignant_count"    : int — class 3 (Malignant Epithelial)
            "inflammatory_count" : int — class 1 (Inflammatory)
            "healthy_count"      : int — class 2 (Healthy Epithelial)
            "stromal_count"      : int — class 4 (Stromal)
            "other_count"        : int — class 0 (Other/Misc)
            "nuclei_details"     : list of dicts with bbox, class_id, class_name
            "processing_time_sec": float

    Raises:
        RuntimeError: if load_models() has not been called first.
        FileNotFoundError: if image_path does not exist.
    """
    if not _models:
        raise RuntimeError(
            "Models not loaded. Call load_models() before run_inference()."
        )

    image_path = str(image_path)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    t_start = time.perf_counter()

    # --- Load image ---
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise ValueError(f"cv2.imread failed to load image: {image_path}")
    img_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # --- Stain normalization ---
    if apply_stain_normalization:
        try:
            img_rgb = _normalizer.normalize(img_rgb)
            logger.debug("Macenko stain normalization applied.")
        except Exception as exc:
            logger.warning("Stain normalization failed (%s) — using raw image.", exc)

    # --- Stage 1: Segmentation ---
    logger.debug("Running U-Net segmentation …")
    binary_mask = _predict_segmentation(img_rgb)

    # --- Stage 2: Instance separation ---
    logger.debug("Running Watershed separation …")
    _, nuclei = _separate_nuclei(img_rgb, binary_mask)
    logger.debug("Detected %d nucleus candidates.", len(nuclei))

    # --- Stage 3: Classification ---
    logger.debug("Running CNN classifier …")
    class_ids = _classify_nuclei(nuclei)

    # --- Aggregate counts ---
    counts = {cls_id: 0 for cls_id in range(5)}
    for cls_id in class_ids:
        counts[cls_id] = counts.get(cls_id, 0) + 1

    # --- Build nucleus details list ---
    nuclei_details = [
        {
            "bbox":       nucleus["bbox"],
            "class_id":   cls_id,
            "class_name": CLASS_NAMES.get(cls_id, "Unknown"),
        }
        for nucleus, cls_id in zip(nuclei, class_ids)
    ]

    # --- Overlay image ---
    overlay = _draw_overlay(img_rgb, nuclei, class_ids)

    # --- Optional saves ---
    if save_overlay_path:
        os.makedirs(os.path.dirname(save_overlay_path), exist_ok=True)
        cv2.imwrite(save_overlay_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        logger.info("Overlay saved to %s", save_overlay_path)

    if save_mask_path:
        os.makedirs(os.path.dirname(save_mask_path), exist_ok=True)
        cv2.imwrite(save_mask_path, (binary_mask * 255).astype(np.uint8))
        logger.info("Mask saved to %s", save_mask_path)

    elapsed = time.perf_counter() - t_start
    logger.info("Inference complete in %.2f s — %d nuclei found.", elapsed, len(nuclei))

    return {
        "overlay_image":       overlay,
        "mask_image":          binary_mask,
        "total_nuclei":        len(nuclei),
        "malignant_count":     counts[3],
        "inflammatory_count":  counts[1],
        "healthy_count":       counts[2],
        "stromal_count":       counts[4],
        "other_count":         counts[0],
        "nuclei_details":      nuclei_details,
        "processing_time_sec": round(elapsed, 2),
    }
