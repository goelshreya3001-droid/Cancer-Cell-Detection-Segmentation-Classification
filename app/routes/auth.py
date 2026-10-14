"""
Authentication routes blueprint.

Endpoints:
    POST /signup
    POST /login
    POST /logout
    GET  /me       — return current session user info (for frontend)
"""

import re
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from ..database import create_user, get_user_by_username, get_user_by_email

auth_bp = Blueprint("auth", __name__)

# Simple RFC-5322-lite pattern (good enough for backend gating)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalise_email(raw: str) -> str:
    """Strip whitespace and lowercase the email address."""
    return raw.strip().lower()


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """
    Register a new user.
    Requires: username, email, password, confirm_password
    Email is mandatory, must be valid, unique (case-insensitive).
    """
    data = request.json if request.is_json else request.form
    username         = data.get("username", "").strip()
    email_raw        = data.get("email", "").strip()
    email            = _normalise_email(email_raw) if email_raw else ""
    password         = data.get("password", "")
    confirm          = data.get("confirm_password", "")

    # ── 1. Required fields ────────────────────────────────────────
    if not username or not email or not password or not confirm:
        return jsonify({
            "success": False,
            "error": "All fields are required (username, email, password, confirm_password)."
        }), 400

    # ── 2. Username length ────────────────────────────────────────
    if len(username) < 3:
        return jsonify({
            "success": False,
            "error": "Username must be at least 3 characters."
        }), 400

    # ── 3. Email format ───────────────────────────────────────────
    if not _valid_email(email):
        return jsonify({
            "success": False,
            "error": "Please provide a valid email address."
        }), 400

    # ── 4. Password length ────────────────────────────────────────
    if len(password) < 4:
        return jsonify({
            "success": False,
            "error": "Password must be at least 4 characters."
        }), 400

    # ── 5. Password match ─────────────────────────────────────────
    if password != confirm:
        return jsonify({
            "success": False,
            "error": "Passwords do not match."
        }), 400

    # ── 6. Duplicate username (case-sensitive, preserved) ─────────
    if get_user_by_username(username):
        return jsonify({
            "success": False,
            "error": "This username is already taken. Please choose another."
        }), 409

    # ── 7. Duplicate email (case-insensitive) ─────────────────────
    if get_user_by_email(email):
        return jsonify({
            "success": False,
            "error": "An account with this email address already exists."
        }), 409

    # ── 8. Hash password and save ─────────────────────────────────
    password_hash = generate_password_hash(password)
    user_id = create_user(username, password_hash, email=email)

    if user_id == -1:
        # Race condition / integrity error fallback
        return jsonify({
            "success": False,
            "error": "Username or email already exists."
        }), 409

    return jsonify({"success": True, "message": "Account created successfully."}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate a user and create a session.
    Requires: username, password
    """
    data = request.json if request.is_json else request.form
    identifier = data.get("username", "").strip()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"success": False, "error": "Username/Email and password are required."}), 400

    # Try looking up by username first
    user = get_user_by_username(identifier)
    # If not found, treat the identifier as an email (trim & lower‑case)
    if user is None:
        email_norm = _normalise_email(identifier)
        user = get_user_by_email(email_norm)

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "error": "Invalid username or password."}), 401

    session.clear()
    session["user_id"]  = user["id"]
    session["username"] = user["username"]

    return jsonify({"success": True, "message": "Logged in successfully."}), 200


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear the current user session."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    """Return current authenticated user info for the frontend."""
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in."}), 401

    user = get_user_by_username(session["username"])
    if user is None:
        session.clear()
        return jsonify({"success": False, "error": "User not found."}), 401

    return jsonify({
        "success":    True,
        "username":   user["username"],
        "email":      user["email"] if "email" in user.keys() else None,
        "created_at": user["created_at"],
    }), 200
