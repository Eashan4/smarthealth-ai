"""Flask app factory. Run with: python -m backend.app"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, send_from_directory

from backend.database.db import init_db
from backend.routes.api_routes import api_bp
from backend.routes.sensor_routes import sensor_bp

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


def create_app() -> Flask:
    # static_folder=None: Flask's default static handling points at a
    # backend/static/ directory that doesn't exist and would otherwise
    # shadow the dashboard_static route below (matching /static/<path> first
    # and 404ing instead of falling through to it).
    app = Flask(__name__, static_folder=None)
    init_db()

    app.register_blueprint(sensor_bp)
    app.register_blueprint(api_bp)

    @app.route("/")
    def dashboard_index():
        return send_from_directory(DASHBOARD_DIR, "index.html")

    @app.route("/static/<path:filename>")
    def dashboard_static(filename):
        return send_from_directory(DASHBOARD_DIR / "static", filename)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
