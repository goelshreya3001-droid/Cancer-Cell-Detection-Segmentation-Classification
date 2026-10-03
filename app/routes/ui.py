from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for

ui_bp = Blueprint("ui", __name__)

def login_required_ui(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("ui.login"))
        return f(*args, **kwargs)
    return decorated_function

@ui_bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("ui.dashboard"))
    return render_template("landing.html")

@ui_bp.route("/login")
def login():
    if "user_id" in session:
        return redirect(url_for("ui.dashboard"))
    return render_template("login.html")

@ui_bp.route("/signup")
def signup():
    if "user_id" in session:
        return redirect(url_for("ui.dashboard"))
    return render_template("signup.html")

@ui_bp.route("/dashboard")
@login_required_ui
def dashboard():
    return render_template("dashboard.html")

@ui_bp.route("/analyze")
@login_required_ui
def analyze():
    return render_template("analyze.html")

@ui_bp.route("/results/<int:analysis_id>")
@login_required_ui
def results(analysis_id):
    return render_template("results.html", analysis_id=analysis_id)

@ui_bp.route("/history_page")
@login_required_ui
def history_page():
    return render_template("history.html")

@ui_bp.route("/profile")
@login_required_ui
def profile():
    return render_template("profile.html")

@ui_bp.route("/about")
def about():
    return render_template("about.html")
