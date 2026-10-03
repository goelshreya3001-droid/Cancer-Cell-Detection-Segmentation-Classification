"""
Flask application factory.

Call create_app() to get a configured Flask instance.
Models are loaded once here at startup so every request reuses them.
"""

import os
import logging

from flask import Flask

from .config import Config
from .database import init_db, close_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def create_app(config_class=Config) -> Flask:
    """
    Application factory.

    Creates and configures the Flask app:
      1. Loads Config
      2. Ensures upload/results directories exist
      3. Initialises the SQLite database
      4. Loads ML models into memory (once, at startup)
      5. Registers all blueprints
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    # ── Ensure storage directories exist ──────────────────────────────────
    os.makedirs(app.config["UPLOAD_FOLDER"],  exist_ok=True)
    os.makedirs(app.config["RESULTS_FOLDER"], exist_ok=True)

    # ── Database ───────────────────────────────────────────────────────────
    init_db(app)
    app.teardown_appcontext(close_db)

    # ── Load ML models (blocking, happens once at process startup) ─────────
    logger.info("Loading ML models at startup...")
    from .ml.inference import load_models
    load_models()
    logger.info("ML models ready.")

    # ── Register blueprints ────────────────────────────────────────────────
    from .routes.api import api_bp
    app.register_blueprint(api_bp)
    
    from .routes.ui import ui_bp
    app.register_blueprint(ui_bp)

    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    logger.info("Flask app created. Routes registered.")
    return app
