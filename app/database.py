"""
SQLite database helpers.

Uses Python's built-in sqlite3 — no extra packages needed.

Schema (single table):
    analyses — one row per image analysis job.
"""

import sqlite3
from flask import g, current_app


# ---------------------------------------------------------------------------
# Connection management  (Flask application-context pattern)
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """
    Return the database connection for the current request context.
    Opens a new connection if one does not already exist.
    """
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE_PATH"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        # Return rows as dict-like objects (row["column"] syntax)
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(error=None) -> None:
    """Close the database connection at the end of every request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT,
    password_hash TEXT NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER,
    original_filename   TEXT    NOT NULL,
    upload_path         TEXT    NOT NULL,
    overlay_path        TEXT    NOT NULL,
    mask_path           TEXT    NOT NULL,
    total_nuclei        INTEGER NOT NULL DEFAULT 0,
    malignant_count     INTEGER NOT NULL DEFAULT 0,
    inflammatory_count  INTEGER NOT NULL DEFAULT 0,
    healthy_count       INTEGER NOT NULL DEFAULT 0,
    stromal_count       INTEGER NOT NULL DEFAULT 0,
    other_count         INTEGER NOT NULL DEFAULT 0,
    processing_time_sec REAL,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
"""


def init_db(app) -> None:
    """
    Create the database tables if they do not already exist.
    Safely migrates existing tables by checking for missing columns.
    Called once from the Flask app factory.
    """
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE_PATH"])
        
        # 1. Create tables if they don't exist
        db.executescript(SCHEMA)
        
        # 2. Safe migration for existing 'analyses' table
        cursor = db.execute("PRAGMA table_info(analyses)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "user_id" not in columns:
            db.execute("ALTER TABLE analyses ADD COLUMN user_id INTEGER REFERENCES users(id)")

        # 3. Safe migration: add email column to users if missing
        cursor_u = db.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in cursor_u.fetchall()]
        if "email" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN email TEXT")

        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def save_analysis(
    original_filename: str,
    upload_path: str,
    overlay_path: str,
    mask_path: str,
    total_nuclei: int,
    malignant_count: int,
    inflammatory_count: int,
    healthy_count: int,
    stromal_count: int,
    other_count: int,
    processing_time_sec: float,
    user_id: int | None = None,
) -> int:
    """
    Insert one analysis record and return the new row id.
    user_id is optional for backwards compatibility with existing unauthenticated routes.
    """
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO analyses (
            user_id, original_filename, upload_path, overlay_path, mask_path,
            total_nuclei, malignant_count, inflammatory_count,
            healthy_count, stromal_count, other_count,
            processing_time_sec
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id, original_filename, upload_path, overlay_path, mask_path,
            total_nuclei, malignant_count, inflammatory_count,
            healthy_count, stromal_count, other_count,
            processing_time_sec,
        ),
    )
    db.commit()
    return cursor.lastrowid


def get_analysis(analysis_id: int, user_id: int | None = None) -> sqlite3.Row | None:
    """
    Fetch a single analysis by id.
    If user_id is provided, enforces that the record belongs to the user.
    """
    db = get_db()
    if user_id is not None:
        return db.execute(
            "SELECT * FROM analyses WHERE id = ? AND user_id = ?", 
            (analysis_id, user_id)
        ).fetchone()
    
    return db.execute(
        "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
    ).fetchone()


def get_all_analyses(limit: int = 50, user_id: int | None = None) -> list[sqlite3.Row]:
    """
    Return the most recent `limit` analyses, newest first.
    If user_id is provided, returns only analyses belonging to that user.
    """
    db = get_db()
    if user_id is not None:
        return db.execute(
            "SELECT * FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", 
            (user_id, limit)
        ).fetchall()
        
    return db.execute(
        "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


# ---------------------------------------------------------------------------
# User management helpers
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str, email: str | None = None) -> int:
    """Create a new user and return their id. Returns -1 if username exists."""
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return -1


def get_user_by_username(username: str) -> sqlite3.Row | None:
    """Fetch a user by username."""
    db = get_db()
    return db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
