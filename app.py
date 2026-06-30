"""
app.py
Crucible — application entry point.

Responsibilities:
  - Create and configure the Flask app
  - Register blueprints
  - Serve the static frontend from /static/
  - Launch the dev server when run directly

Usage:
  python app.py                          # Dev server with auto-reload
  FLASK_ENV=production flask run         # Production (use a real WSGI server)
"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from routes.api import api_bp

# Load .env variables into the process environment before anything else reads them
load_dotenv()

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    CORS(app)

    # Register blueprints
    app.register_blueprint(api_bp)

    # Serve the single-page frontend for every non-API route
    @app.route("/")
    def index():
        return send_from_directory("static", "index.html")

    # Catch-all so that browser navigation (e.g. refresh on a hash route) still works
    @app.errorhandler(404)
    def not_found(_err):
        return send_from_directory("static", "index.html")

    return app


# ---------------------------------------------------------------------------
# Dev server entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()

    host  = os.getenv("HOST", "0.0.0.0")
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"

    print("=" * 62)
    print("  Crucible — AI Engineering Debate System")
    print("=" * 62)
    print(f"  App:    http://localhost:{port}")
    print(f"  Debug:  {debug}")

    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        print(f"  Groq:   ✓  Key loaded from .env ({groq_key[:8]}...)")
    else:
        print("  Groq:   ⚠  No GROQ_API_KEY found in .env — add it and restart")

    print("=" * 62)

    app.run(host=host, port=port, debug=debug, threaded=True)