"""AI Mock Interviewer - Flask application entry point."""
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from db.database import init_db
from routes.answer_routes import answer_bp
from routes.question_routes import question_bp
from routes.report_routes import report_bp
from routes.resume_routes import resume_bp


def create_app():
    app = Flask(__name__)
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

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
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
            }
        )

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": f"File exceeds {Config.MAX_UPLOAD_MB} MB limit"}), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
