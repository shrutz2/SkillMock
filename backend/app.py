"""AI Mock Interviewer - Flask application entry point."""
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import Config
from db.database import init_db
from routes.answer_routes import answer_bp
from routes.question_routes import question_bp
from routes.report_routes import report_bp
from routes.resume_routes import resume_bp
from services import embedding_service

# When the React build is present (single-container deploy) Flask serves it,
# so the whole app runs behind one URL.
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
SERVE_FRONTEND = os.path.isdir(STATIC_DIR)


def create_app():
    app = Flask(__name__, static_folder=STATIC_DIR if SERVE_FRONTEND else None,
                static_url_path="")
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024

    # Only the configured frontend may call the API from a browser. A wildcard
    # would let any site issue requests on a visitor's behalf.
    CORS(
        app,
        resources={r"/api/*": {"origins": Config.ALLOWED_ORIGINS}},
        allow_headers=["Content-Type", "Authorization", "X-Session-Token"],
        methods=["GET", "POST", "OPTIONS"],
        max_age=600,
    )

    # A pure API can lock everything down; when Flask also serves the React
    # build it needs to allow the app's own assets and the webfonts.
    if SERVE_FRONTEND:
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
    else:
        csp = "default-src 'none'; frame-ancestors 'none'"

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        resp.headers["Content-Security-Policy"] = csp
        # API responses carry session data; static assets can be cached.
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    init_db()

    app.register_blueprint(resume_bp)
    app.register_blueprint(question_bp)
    app.register_blueprint(answer_bp)
    app.register_blueprint(report_bp)

    @app.route("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "db_backend": Config.DB_BACKEND,
                "llm_provider": Config.LLM_PROVIDER,
                "embedding_model": Config.EMBEDDING_MODEL,
                "embedding_backend": embedding_service.backend_name(),
            }
        )

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": f"File exceeds {Config.MAX_UPLOAD_MB} MB limit"}), 413

    if SERVE_FRONTEND:
        @app.route("/")
        def index():
            return send_from_directory(STATIC_DIR, "index.html")

        @app.errorhandler(404)
        def spa_fallback(_):
            # API 404s stay JSON; everything else falls through to the React
            # router so a deep link like /report still loads the app.
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not found"}), 404
            return send_from_directory(STATIC_DIR, "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
