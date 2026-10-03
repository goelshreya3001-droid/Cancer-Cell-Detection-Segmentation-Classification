"""
Configuration for the Flask application.

All tunable settings live here. Environment-specific values can be
overridden by setting the corresponding environment variable before
starting the server.
"""

import os

# Project root is two levels above this file: app/config.py -> app/ -> project/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    # ------------------------------------------------------------------ #
    # Security                                                             #
    # ------------------------------------------------------------------ #
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # ------------------------------------------------------------------ #
    # File upload                                                          #
    # ------------------------------------------------------------------ #
    UPLOAD_FOLDER  = os.path.join(BASE_DIR, "app", "static", "uploads")
    RESULTS_FOLDER = os.path.join(BASE_DIR, "app", "static", "results")

    # Allowed image extensions (case-insensitive)
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "tif", "bmp"}

    # Max upload size: 32 MB  (histopathology tiles can be large)
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    DATABASE_PATH = os.path.join(BASE_DIR, "pathology.db")

    # ------------------------------------------------------------------ #
    # ML models                                                            #
    # ------------------------------------------------------------------ #
    # Models are loaded at app startup via app.ml.inference.load_models()
    # Paths are resolved inside inference.py relative to the project root.

    # ------------------------------------------------------------------ #
    # Debug / development                                                  #
    # ------------------------------------------------------------------ #
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
