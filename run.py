"""
Application entry point.

Run with:
    python run.py

The server starts at  http://localhost:5000
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=app.config["DEBUG"],
        # use_reloader=False prevents models from loading twice in debug mode
        use_reloader=False,
    )
