"""
API routes blueprint.

Endpoints:
    GET  /health        — liveness check
    POST /predict       — run full ML inference on an uploaded image
    GET  /history       — list recent analyses (JSON)
    GET  /analysis/<id> — fetch one analysis by id (JSON)
"""

import os
import uuid
import logging
import traceback

from functools import wraps
from flask import Blueprint, request, jsonify, current_app, session

from ..database import save_analysis, get_analysis, get_all_analyses
from ..ml.inference import run_inference

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


def login_required(f):
    """Decorator to require an authenticated session for an API endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed image extension."""
    allowed = current_app.config["ALLOWED_EXTENSIONS"]
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed
    )


def _static_url(abs_path: str) -> str:
    """
    Convert an absolute file-system path inside app/static/ to a
    URL that Flask's built-in static file serving can handle.

    Example:
        .../app/static/uploads/abc.png  ->  /static/uploads/abc.png
    """
    static_folder = current_app.static_folder  # .../app/static
    rel = os.path.relpath(abs_path, static_folder).replace("\\", "/")
    return f"/static/{rel}"


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health():
    """
    Liveness check.

    Returns:
        200  {"status": "ok", "message": "Service is running"}
    """
    return jsonify({"status": "ok", "message": "Service is running"}), 200


# ---------------------------------------------------------------------------
# POST /predict
# ---------------------------------------------------------------------------

@api_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    """
    Run the full two-stage ML pipeline on an uploaded histopathology image.

    Request (multipart/form-data):
        image  — the image file (PNG / JPG / TIFF / BMP)

    Response 200:
        {
            "success": true,
            "analysis_id": <int>,
            ...
        }
    """

    # ── 1. Validate request ───────────────────────────────────────────────
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "No file field named 'image' found in the request."
        }), 400

    file = request.files["image"]

    if file.filename == "" or file.filename is None:
        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    if not _allowed_file(file.filename):
        allowed = ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"]))
        return jsonify({
            "success": False,
            "error": f"Invalid file type. Allowed extensions: {allowed}"
        }), 400

    # ── 2. Save the uploaded file with a unique name ──────────────────────
    ext          = file.filename.rsplit(".", 1)[1].lower()
    job_id       = uuid.uuid4().hex          # e.g. "3f8a1b2c..."
    safe_name    = f"{job_id}_{os.path.basename(file.filename)}"
    upload_path  = os.path.join(current_app.config["UPLOAD_FOLDER"], safe_name)

    file.save(upload_path)
    logger.info("Saved upload: %s", upload_path)

    # ── 3. Determine output paths ─────────────────────────────────────────
    results_dir  = current_app.config["RESULTS_FOLDER"]
    overlay_path = os.path.join(results_dir, f"{job_id}_overlay.png")
    mask_path    = os.path.join(results_dir, f"{job_id}_mask.png")

    # ── 4. Run ML inference ───────────────────────────────────────────────
    try:
        result = run_inference(
            image_path=upload_path,
            apply_stain_normalization=True,
            save_overlay_path=overlay_path,
            save_mask_path=mask_path,
        )
    except Exception as exc:
        logger.error("Inference failed: %s\n%s", exc, traceback.format_exc())
        # Clean up the orphaned upload on failure
        if os.path.exists(upload_path):
            os.remove(upload_path)
        return jsonify({
            "success": False,
            "error": f"Inference failed: {str(exc)}"
        }), 500

    # ── 5. Persist result in the database ─────────────────────────────────
    try:
        analysis_id = save_analysis(
            original_filename   = file.filename,
            upload_path         = upload_path,
            overlay_path        = overlay_path,
            mask_path           = mask_path,
            total_nuclei        = result["total_nuclei"],
            malignant_count     = result["malignant_count"],
            inflammatory_count  = result["inflammatory_count"],
            healthy_count       = result["healthy_count"],
            stromal_count       = result["stromal_count"],
            other_count         = result["other_count"],
            processing_time_sec = result["processing_time_sec"],
            user_id             = session["user_id"],
        )
    except Exception as exc:
        logger.error("DB write failed: %s", exc)
        # Non-fatal — still return inference results, just without an id
        analysis_id = None

    # ── 6. Build and return JSON response ─────────────────────────────────
    return jsonify({
        "success":             True,
        "analysis_id":         analysis_id,
        "total_nuclei":        result["total_nuclei"],
        "malignant_nuclei":    result["malignant_count"],
        "inflammatory_nuclei": result["inflammatory_count"],
        "healthy_nuclei":      result["healthy_count"],
        "stromal_nuclei":      result["stromal_count"],
        "other_nuclei":        result["other_count"],
        "processing_time_sec": result["processing_time_sec"],
        "overlay_url":         _static_url(overlay_path),
        "mask_url":            _static_url(mask_path),
        "upload_url":          _static_url(upload_path),
    }), 200


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

@api_bp.route("/history", methods=["GET"])
@login_required
def history():
    """
    Return the most recent 50 analyses for the logged-in user as JSON.
    """
    rows = get_all_analyses(limit=50, user_id=session["user_id"])
    analyses = []
    for row in rows:
        analyses.append({
            "id":                   row["id"],
            "original_filename":    row["original_filename"],
            "total_nuclei":         row["total_nuclei"],
            "malignant_count":      row["malignant_count"],
            "inflammatory_count":   row["inflammatory_count"],
            "healthy_count":        row["healthy_count"],
            "stromal_count":        row["stromal_count"],
            "other_count":          row["other_count"],
            "processing_time_sec":  row["processing_time_sec"],
            "overlay_url":          _static_url(row["overlay_path"]),
            "upload_url":           _static_url(row["upload_path"]),
            "created_at":           row["created_at"],
        })

    return jsonify({
        "success":  True,
        "count":    len(analyses),
        "analyses": analyses,
    }), 200


# ---------------------------------------------------------------------------
# GET /analysis/<id>
# ---------------------------------------------------------------------------

@api_bp.route("/analysis/<int:analysis_id>", methods=["GET"])
@login_required
def get_analysis_by_id(analysis_id: int):
    """
    Fetch one analysis record by its id, provided it belongs to the logged-in user.
    """
    row = get_analysis(analysis_id, user_id=session["user_id"])

    if row is None:
        return jsonify({
            "success": False,
            "error":   f"Analysis id {analysis_id} not found or unauthorized."
        }), 404

    return jsonify({
        "success":             True,
        "id":                  row["id"],
        "original_filename":   row["original_filename"],
        "total_nuclei":        row["total_nuclei"],
        "malignant_count":     row["malignant_count"],
        "inflammatory_count":  row["inflammatory_count"],
        "healthy_count":       row["healthy_count"],
        "stromal_count":       row["stromal_count"],
        "other_count":         row["other_count"],
        "processing_time_sec": row["processing_time_sec"],
        "overlay_url":         _static_url(row["overlay_path"]),
        "mask_url":            _static_url(row["mask_path"]),
        "upload_url":          _static_url(row["upload_path"]),
        "created_at":          row["created_at"],
    }), 200
