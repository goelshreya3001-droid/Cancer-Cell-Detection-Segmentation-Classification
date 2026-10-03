"""
ML inference package for cancer nuclei detection, segmentation, and classification.

Extracted from Jupyter notebooks — original notebook code is NOT modified.
Notebook sources:
  - 02_train_unet.ipynb        → models.py (UNet)
  - 04_nuclei_classification.ipynb → models.py (NucleiClassifier)
  - stain_utils.ipynb          → stain_utils.py (MacenkoNormalizer)
  - 03_evaluate_unet.ipynb     → inference.py (watershed pipeline)
  - evaluate_generalization.ipynb → inference.py (sliding-window tiling)
"""

from .inference import run_inference, load_models

__all__ = ["run_inference", "load_models"]
