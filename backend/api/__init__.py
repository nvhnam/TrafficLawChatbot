from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS


def create_app() -> Flask:
    static_dir = Path(__file__).parent.parent / "static"

    app = Flask(__name__, static_folder=str(static_dir), static_url_path="/assets")
    CORS(app)

    # ── Register blueprints ────────────────────────────────────────────────────
    from backend.api.blueprints.chat import bp as chat_bp
    from backend.api.blueprints.documents import bp as docs_bp
    from backend.api.blueprints.ingest import bp as ingest_bp
    from backend.api.blueprints.ocr_bp import bp as ocr_bp

    app.register_blueprint(chat_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(ocr_bp)

    # Pre-warm the bot so the SentenceTransformer model loads at startup,
    # not mid-request (a native crash there would kill the whole server silently).
    try:
        from backend.chatbot.bot import GraphRAG_Bot
        from backend.core.container import ServiceContainer
        ServiceContainer.get("bot", GraphRAG_Bot)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Bot pre-warm failed: %s", exc, exc_info=True)

    # ── Serve React SPA (built files go to backend/static/) ───────────────────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        index = static_dir / "index.html"
        if index.exists():
            return send_from_directory(str(static_dir), "index.html")
        return (
            "Frontend not built. Run: cd frontend && npm run build",
            404,
        )

    return app
