"""
Authentication routes blueprint.

Endpoints:
    POST /signup
    POST /login
    POST /logout
    GET  /me       — return current session user info (for frontend)
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from ..database import create_user, get_user_by_username

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """
    Register a new user.
    Requires: username, password, confirm_password
    Optional: email
    """
    data = request.json if request.is_json else request.form
    username = data.get("username", "").strip()
    email = data.get("email", "").strip() or None
    password = data.get("password")
    confirm = data.get("confirm_password")

    # 1. Basic validation
    if not username or not password or not confirm:
        return jsonify({"success": False, "error": "Missing required fields (username, password, confirm_password)."}), 400

    if len(username) < 3:
        return jsonify({"success": False, "error": "Username must be at least 3 characters."}), 400

    if len(password) < 4:
        return jsonify({"success": False, "error": "Password must be at least 4 characters."}), 400

    if password != confirm:
        return jsonify({"success": False, "error": "Passwords do not match."}), 400

    # 2. Check for existing username
    existing_user = get_user_by_username(username)
    if existing_user:
        return jsonify({"success": False, "error": "Username already exists."}), 409

    # 3. Hash the password securely (never store plain text)
    password_hash = generate_password_hash(password)

    # 4. Save to database
    user_id = create_user(username, password_hash, email=email)

    if user_id == -1:
        return jsonify({"success": False, "error": "Username already exists."}), 409

    return jsonify({"success": True, "message": "User created successfully."}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate a user and create a session.
    Requires: username, password
    """
    data = request.json if request.is_json else request.form
    username = data.get("username", "").strip()
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "error": "Missing username or password."}), 400

    # 1. Fetch user from DB
    user = get_user_by_username(username)

    # 2. Verify password hash
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"success": False, "error": "Invalid username or password."}), 401

    # 3. Create session
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify({"success": True, "message": "Logged in successfully."}), 200


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Clear the current user session.
    """
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    """
    Return current authenticated user info for the frontend.
    """
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in."}), 401

    user = get_user_by_username(session["username"])
    if user is None:
        session.clear()
        return jsonify({"success": False, "error": "User not found."}), 401

    return jsonify({
        "success": True,
        "username": user["username"],
        "email": user["email"] if "email" in user.keys() else None,
        "created_at": user["created_at"],
    }), 200
